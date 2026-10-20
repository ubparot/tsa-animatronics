"""Clause-by-clause speech: voice the reply while the model is still writing it.

    Ollama (text GPU) --tokens--> ClausePlanner --chunks--> synthesis thread
        (voice GPU, Chatterbox) --audio--> playback thread --> speaker

Chatterbox Turbo returns whole clips, so the unit of streaming is a clause, not
a word: the first short clause is synthesized and starts playing while the next
one is being synthesized. On the show PC the two models sit on different cards
(machine.json "gpus"); only text crosses between them, over Ollama's HTTP API.

--simulate-show-pc reproduces that PC on a single larger GPU: it caps the voice
process's VRAM to the 3070's 8 GB and slows each side to approximate the
2060/3070 speed, so gaps between clauses show up before the event does.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import sounddevice as sd
import soundfile as sf

from pipeline import (
    MODEL_TEXT_SCHEMA,
    build_ollama_request,
    fallback_response,
    make_show_packet,
    remember_spoken_line,
    show_bank_response,
    validate_packet,
)
from streaming_text import ClausePlanner, SpokenTextExtractor
from tts_chatterbox import VoiceEngine


OLLAMA_URL = "http://127.0.0.1:11434"

# The whole-line request caps spoken_text at 108 characters in the JSON
# grammar, which chops an over-long reply mid-word ("too long for a carp").
# The whole-line path can retry; a streamed reply is already playing. So the
# grammar gets room to finish its sentence, and ClausePlanner enforces the
# 110-character show contract by ending at a sentence or clause instead.
STREAM_TEXT_SCHEMA = {
    **MODEL_TEXT_SCHEMA,
    "properties": {"spoken_text": {"type": "string", "maxLength": 240}},
}

# Rough RTX 5080 -> show PC ratios from memory bandwidth, which bounds both
# token-by-token models (5080 960 GB/s, 3070 448 GB/s, 2060 336 GB/s). They
# are estimates: replace them with the ratio stream_check.py measures on the
# real show PC.
SHOW_PC = {"text_vram_gb": 6.0, "voice_vram_gb": 8.0, "text_slowdown": 3.0, "voice_slowdown": 1.8}


@dataclass
class StreamSettings:
    first_chunk_words: int = 6
    output_device: int | str | None = None
    play: bool = True
    text_slowdown: float = 1.0
    voice_slowdown: float = 1.0

    @classmethod
    def from_config(cls, config: dict[str, Any], simulate_show_pc: bool = False, play: bool = True) -> "StreamSettings":
        return cls(
            first_chunk_words=int(config.get("stream_first_chunk_words", 6)),
            output_device=config.get("output_device"),
            play=play,
            text_slowdown=SHOW_PC["text_slowdown"] if simulate_show_pc else 1.0,
            voice_slowdown=SHOW_PC["voice_slowdown"] if simulate_show_pc else 1.0,
        )


@dataclass
class SpeechReport:
    """Timeline of one streamed reply, in seconds from the start of the turn."""

    chunks: list[dict[str, Any]] = field(default_factory=list)
    first_text_s: float | None = None
    text_done_s: float | None = None
    first_audio_s: float | None = None
    speech_end_s: float | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def gap_total_s(self) -> float:
        return sum(chunk["gap_s"] for chunk in self.chunks)

    def as_dict(self) -> dict[str, Any]:
        rounded = lambda value: None if value is None else round(value, 3)  # noqa: E731
        return {
            "first_text_s": rounded(self.first_text_s),
            "text_done_s": rounded(self.text_done_s),
            "first_audio_s": rounded(self.first_audio_s),
            "speech_end_s": rounded(self.speech_end_s),
            "gap_total_s": round(self.gap_total_s, 3),
            "chunks": self.chunks,
            "errors": self.errors,
        }


class ChunkedSpeaker:
    """Synthesize planned chunks on one thread and play them back-to-back on another.

    The synthesis thread pulls text from a ClausePlanner instead of receiving
    fixed clauses: each time it is free it asks for as much text as it can
    voice before the audio already queued runs out, using the speed it has
    measured so far. That keeps playback continuous on a slow voice GPU.
    """

    # Before anything is measured, assume the voice runs at real time and
    # speaks ~14 characters per second; both are replaced by measurements.
    DEFAULT_RTF = 1.0
    DEFAULT_CHARS_PER_S = 14.0
    # Ask for a little less than the slack so timing noise does not cause gaps.
    SAFETY = 0.85

    def __init__(self, voice: VoiceEngine, settings: StreamSettings, started_at: float) -> None:
        self.voice = voice
        self.settings = settings
        self.started_at = started_at
        self.report = SpeechReport()
        self.planner = ClausePlanner(first_chunk_words=settings.first_chunk_words)
        self._changed = threading.Condition()
        self._audio_queue: queue.Queue[np.ndarray | None] = queue.Queue()
        self._samples: list[np.ndarray] = []
        self._synth_s = 0.0
        self._audio_s = 0.0
        self._chars = 0
        # When the audio handed to the speaker so far will have finished, in
        # seconds from the start of the turn. A chunk ready later is a gap.
        self._play_end: float | None = None
        self._threads = [
            threading.Thread(target=self._synthesize_loop, daemon=True),
            threading.Thread(target=self._playback_loop, daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def say(self, text: str) -> None:
        with self._changed:
            self.planner.push(text)
            self._changed.notify()

    def end_text(self) -> None:
        with self._changed:
            self.planner.finish()
            self._changed.notify()

    def finish(self, wav_path: Path | None = None) -> SpeechReport:
        """Wait until all text has been spoken, then save the whole reply."""
        self.end_text()
        for thread in self._threads:
            thread.join()
        self.report.speech_end_s = self._play_end
        if wav_path is not None and self._samples:
            wav_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(wav_path), np.concatenate(self._samples), self.voice.sample_rate, subtype="PCM_16")
        return self.report

    def _elapsed(self) -> float:
        return time.perf_counter() - self.started_at

    def _char_budget(self) -> int | None:
        if self._play_end is None:
            return None
        slack_s = max(0.0, self._play_end - self._elapsed())
        rtf = self._synth_s / self._audio_s if self._audio_s else self.DEFAULT_RTF
        chars_per_s = self._chars / self._audio_s if self._audio_s else self.DEFAULT_CHARS_PER_S
        return int(slack_s / max(rtf, 0.05) * chars_per_s * self.SAFETY)

    def _next_text(self) -> str | None:
        with self._changed:
            while True:
                text = self.planner.next_chunk(self._char_budget())
                if text is not None or self.planner.done:
                    return text
                # Re-check periodically: the budget shrinks as audio plays.
                self._changed.wait(timeout=0.05)

    def _synthesize_loop(self) -> None:
        try:
            while (text := self._next_text()) is not None:
                started = time.perf_counter()
                try:
                    samples = self.voice.synthesize_samples(text)
                except Exception as exc:  # one bad chunk must not silence the rest
                    self.report.errors.append(f"voice failed on {text!r}: {exc}")
                    continue
                synth_s = time.perf_counter() - started
                if self.settings.voice_slowdown > 1:
                    time.sleep(synth_s * (self.settings.voice_slowdown - 1))
                    synth_s = time.perf_counter() - started
                ready_at = self._elapsed()
                audio_s = samples.size / self.voice.sample_rate
                gap_s = 0.0 if self._play_end is None else max(0.0, ready_at - self._play_end)
                start = ready_at if self._play_end is None else max(ready_at, self._play_end)
                if self.report.first_audio_s is None:
                    self.report.first_audio_s = start
                with self._changed:
                    self._play_end = start + audio_s
                    self._synth_s += synth_s
                    self._audio_s += audio_s
                    self._chars += len(text)
                self.report.chunks.append({
                    "text": text,
                    "synth_s": round(synth_s, 3),
                    "audio_s": round(audio_s, 3),
                    "ready_s": round(ready_at, 3),
                    "gap_s": round(gap_s, 3),
                })
                self._samples.append(samples)
                self._audio_queue.put(samples)
        finally:
            self._audio_queue.put(None)

    def _playback_loop(self) -> None:
        if not self.settings.play:
            while self._audio_queue.get() is not None:
                pass
            return
        with sd.OutputStream(
            samplerate=self.voice.sample_rate,
            channels=1,
            dtype="float32",
            device=self.settings.output_device,
        ) as stream:
            while (samples := self._audio_queue.get()) is not None:
                stream.write(samples.astype(np.float32).reshape(-1, 1))
            # Leaving the block stops the stream, which first drains its buffer.


def stream_spoken_text(payload: dict[str, Any], timeout: float, text_slowdown: float = 1.0) -> Iterator[str]:
    """Yield spoken_text characters from Ollama as the model produces them."""
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps({**payload, "stream": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    extractor = SpokenTextExtractor()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        previous = time.perf_counter()
        for line in response:
            if text_slowdown > 1:
                time.sleep((time.perf_counter() - previous) * (text_slowdown - 1))
                previous = time.perf_counter()
            event = json.loads(line)
            if event.get("error"):
                raise ValueError(f"Ollama error: {event['error']}")
            text = extractor.feed(event.get("message", {}).get("content", ""))
            if text:
                yield text
            if extractor.done or event.get("done"):
                return


@dataclass
class StreamedTurn:
    packet: dict[str, Any]
    source: str
    report: SpeechReport


def speak_streamed_turn(
    question: str,
    turn: int,
    model: str | None,
    timeout: float,
    tag_override: str | None,
    voice: VoiceEngine,
    settings: StreamSettings,
    wav_path: Path | None = None,
    started_at: float | None = None,
) -> StreamedTurn:
    """Answer one question, speaking each chunk as soon as it is ready.

    Show-bank and fallback lines are known in full up front, but still go
    through the planner so their first clause also plays sooner. A model reply
    cannot be retried once its first clause is playing, so the whole-line
    repeat check in call_ollama does not apply here; the response contract is
    still validated on the finished line.
    """
    started_at = time.perf_counter() if started_at is None else started_at
    speaker = ChunkedSpeaker(voice, settings, started_at)
    report = speaker.report
    tag: str | None = None
    packet = show_bank_response(question, turn, tag_override)
    source = "show_bank"
    if packet is not None:
        speaker.say(packet["spoken_text"])
    elif model:
        tag, _message, payload = build_ollama_request(question, model, tag_override, turn)
        payload["format"] = STREAM_TEXT_SCHEMA
        source = "ollama_stream"
        try:
            for text in stream_spoken_text(payload, timeout, settings.text_slowdown):
                if report.first_text_s is None:
                    report.first_text_s = time.perf_counter() - started_at
                speaker.say(text)
                if speaker.planner.complete:  # hit the line-length limit
                    break
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            report.errors.append(f"local model stream failed: {exc}")
        report.text_done_s = time.perf_counter() - started_at
    if packet is None and not speaker.planner.has_text:
        # Nothing was spoken yet, so a clean scripted line can still replace it.
        packet = fallback_response(question, turn, tag_override)
        source = "fallback"
        speaker.say(packet["spoken_text"])
    speaker.finish(wav_path)
    if packet is None:
        packet = make_show_packet(speaker.planner.spoken_text, tag or "TRUTH", f"ollama_{model}")
        ok, reason = validate_packet(packet)
        if not ok:
            report.errors.append(f"streamed packet invalid: {reason}")
    return StreamedTurn(remember_spoken_line(packet), source, report)


def ollama_vram_gb(model: str) -> float | None:
    """VRAM Ollama reports for a loaded model, or None if it is not loaded."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=2) as response:
            loaded = json.loads(response.read().decode("utf-8")).get("models", [])
    except (OSError, ValueError):
        return None
    for entry in loaded:
        if entry.get("name", "").split(":")[0] == model.split(":")[0]:
            return entry.get("size_vram", 0) / 1024**3
    return None
