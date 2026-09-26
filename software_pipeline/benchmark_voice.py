"""Measure voice speed, GPU memory, and intelligibility with the real show stack loaded.

Loads Whisper, the Ollama model, and the configured voice the same way the UI
does, then times every line in eval/test_lines.json. With --questions it also
times full question -> AI -> voice turns. Results and every generated WAV go to
<runtime>/benchmarks/<time>-<computer>[-label]/ so runs from different
computers and voice versions can be compared, and the WAVs reused for blind
listening tests.

Current voices are not streaming, so time to first audio equals synthesis time.
GPU memory is the whole-GPU reading from nvidia-smi (other applications
included), reported relative to a baseline taken before anything loads.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from cuda_runtime import enable_torch_cuda_dlls

# Must happen before CTranslate2 is imported through faster-whisper.
enable_torch_cuda_dlls()

import soundfile as sf  # noqa: E402
from faster_whisper import WhisperModel  # noqa: E402

from machine_paths import MACHINE  # noqa: E402
from pipeline import get_response, warm_ollama_model  # noqa: E402
from tts_chatterbox import create_voice, describe_voice  # noqa: E402
from ui_server import MODEL_TIMEOUTS  # noqa: E402
from voice_pipeline import load_config, transcribe  # noqa: E402


ROOT = Path(__file__).resolve().parent
LINES_PATH = ROOT / "eval" / "test_lines.json"
WORD_PATTERN = re.compile(r"[a-z0-9']+")
TURN_QUESTIONS = [
    "Hello!",
    "What is your favorite color?",
    "What is 7 times 6?",
    "What does the fox say?",
    "Why is the sky blue?",
    "Can you tell me a joke?",
    "Do you ever tell lies?",
    "What did you build today?",
    "What do you dream about?",
    "Are you a real boy?",
]


class GpuMemorySampler:
    """Streams nvidia-smi readings so model-load and synthesis peaks are captured."""

    def __init__(self, interval_ms: int = 200) -> None:
        self.interval_ms = interval_ms
        self.samples: list[tuple[float, int, int]] = []
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> bool:
        try:
            self.process = subprocess.Popen(
                [
                    "nvidia-smi", "--id=0",
                    "--query-gpu=memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                    f"--loop-ms={self.interval_ms}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            return False
        threading.Thread(target=self._read, daemon=True).start()
        return True

    def _read(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        for line in self.process.stdout:
            try:
                used, utilization = (int(value.strip()) for value in line.split(",")[:2])
            except ValueError:
                continue
            self.samples.append((time.perf_counter(), used, utilization))

    def latest(self) -> int | None:
        return self.samples[-1][1] if self.samples else None

    def peak(self, start: float | None = None, end: float | None = None) -> int | None:
        # Pad the window by one sample interval so short syntheses are not missed.
        pad = self.interval_ms / 1000
        values = [
            used for stamp, used, _ in list(self.samples)
            if (start is None or stamp >= start - pad) and (end is None or stamp <= end + pad)
        ]
        return max(values) if values else None

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()


def gpu_info() -> dict[str, str]:
    try:
        output = subprocess.run(
            ["nvidia-smi", "--id=0", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return {}
    name, memory_total, driver = (part.strip() for part in output.split(","))
    return {"name": name, "memory_total": memory_total, "driver": driver}


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    """Word-level edit distance divided by reference length (rough intelligibility check)."""
    ref = WORD_PATTERN.findall(reference.lower())
    hyp = WORD_PATTERN.findall(hypothesis.lower())
    if not ref:
        return None
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, 1):
        current = [i] + [0] * len(hyp)
        for j, hyp_word in enumerate(hyp, 1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ref_word != hyp_word))
        previous = current
    return round(previous[-1] / len(ref), 3)


def percentile(values: list[float], pct: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[index], 3)


def stats(values: list[float]) -> dict[str, float | None]:
    return {"median": percentile(values, 50), "p90": percentile(values, 90), "max": percentile(values, 100)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the configured Pinocchio voice with the full stack loaded.")
    parser.add_argument("--lines", type=Path, default=LINES_PATH, help="Test line file (eval/test_lines.json).")
    parser.add_argument("--limit", type=int, help="Only use the first N lines.")
    parser.add_argument("--repeat", type=int, default=1, help="Synthesize every line this many times.")
    parser.add_argument("--questions", action="store_true", help="Also time question -> AI -> voice turns.")
    parser.add_argument("--model", default="pinocchio-fast", choices=sorted(MODEL_TIMEOUTS), help="Ollama model.")
    parser.add_argument("--label", default="", help="Short name added to the results folder.")
    args = parser.parse_args()

    config = load_config()
    lines = json.loads(args.lines.read_text(encoding="utf-8"))["lines"][: args.limit]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", args.label).strip("-")
    out_dir = MACHINE.runtime / "benchmarks" / "-".join(part for part in (stamp, platform.node(), label) if part)
    wav_dir = out_dir / "wavs"
    wav_dir.mkdir(parents=True, exist_ok=True)

    sampler = GpuMemorySampler()
    if sampler.start():
        time.sleep(1.5)
    baseline_mb = sampler.latest()

    print(f"Loading the show stack (results -> {out_dir})")
    load_seconds: dict[str, float] = {}
    started = time.perf_counter()
    stt = WhisperModel(
        config["whisper_model"],
        device=config["whisper_device"],
        compute_type=config["whisper_compute_type"],
        download_root=str(MACHINE.runtime / "whisper"),
    )
    load_seconds["whisper"] = time.perf_counter() - started
    started = time.perf_counter()
    try:
        warm_ollama_model(args.model)
        ollama_error = None
    except (OSError, TimeoutError, ValueError) as exc:
        ollama_error = str(exc)
        print(f"[could not preload {args.model}: {exc}]")
    load_seconds["ollama"] = time.perf_counter() - started
    started = time.perf_counter()
    voice = create_voice(config)
    load_seconds["voice"] = time.perf_counter() - started
    voice_label = describe_voice(voice)
    loaded_mb = sampler.latest()
    print(f"Voice: {voice_label}")

    # One untimed line so first-call warm-up is not counted as steady-state speed.
    voice.synthesize_to_wav("Warming up the workshop voice.", wav_dir / "_warmup.wav")

    results: list[dict[str, Any]] = []
    total = len(lines) * args.repeat
    for repeat in range(1, args.repeat + 1):
        for line in lines:
            path = wav_dir / f"{line['id']}_r{repeat}.wav"
            error = None
            started = time.perf_counter()
            try:
                voice.synthesize_to_wav(line["text"], path)
            except Exception as exc:  # Record the failure and keep measuring the other lines.
                error = f"{type(exc).__name__}: {exc}"
            finished = time.perf_counter()
            synth_seconds = finished - started
            record: dict[str, Any] = {
                "kind": "line",
                "id": line["id"],
                "category": line["category"],
                "repeat": repeat,
                "text": line["text"],
                "synth_s": round(synth_seconds, 3),
                "first_audio_s": round(synth_seconds, 3),
                "voice_fallback": getattr(voice, "last_error", None),
                "peak_gpu_mb": sampler.peak(started, finished),
                "error": error,
            }
            if error is None:
                audio_seconds = sf.info(str(path)).duration
                stt_started = time.perf_counter()
                heard = transcribe(stt, path)
                record.update(
                    audio_s=round(audio_seconds, 3),
                    rtf=round(synth_seconds / audio_seconds, 3) if audio_seconds else None,
                    stt_s=round(time.perf_counter() - stt_started, 3),
                    heard=heard,
                    wer=word_error_rate(line["text"], heard),
                    wav=str(path.relative_to(out_dir)),
                )
            results.append(record)
            print(
                f"[{len(results)}/{total}] {line['id']:<13} synth {synth_seconds:5.2f}s"
                + (f"  audio {record['audio_s']:5.2f}s  rtf {record['rtf']:.2f}  wer {record['wer']}" if error is None else f"  ERROR {error}")
                + ("  [voice fallback]" if record["voice_fallback"] else "")
            )

    if args.questions:
        for turn, question in enumerate(TURN_QUESTIONS, 1):
            path = wav_dir / f"turn_{turn:02d}.wav"
            started = time.perf_counter()
            packet, source = get_response(question, turn, args.model, MODEL_TIMEOUTS[args.model])
            ai_done = time.perf_counter()
            voice.synthesize_to_wav(packet["spoken_text"], path)
            finished = time.perf_counter()
            record = {
                "kind": "turn",
                "question": question,
                "source": source,
                "spoken_text": packet["spoken_text"],
                "ai_s": round(ai_done - started, 3),
                "voice_s": round(finished - ai_done, 3),
                "total_s": round(finished - started, 3),
                "audio_s": round(sf.info(str(path)).duration, 3),
                "voice_fallback": getattr(voice, "last_error", None),
                "peak_gpu_mb": sampler.peak(started, finished),
                "wav": str(path.relative_to(out_dir)),
            }
            results.append(record)
            print(f"[turn {turn}] {source:<9} ai {record['ai_s']:.2f}s  voice {record['voice_s']:.2f}s  -> {packet['spoken_text']}")

    sampler.stop()
    line_results = [r for r in results if r["kind"] == "line" and r["error"] is None]
    turn_results = [r for r in results if r["kind"] == "turn"]
    peak_mb = sampler.peak()
    summary = {
        "time": stamp,
        "computer": platform.node(),
        "python": sys.version.split()[0],
        "gpu": gpu_info(),
        "voice": voice_label,
        "voice_config": {k: v for k, v in config.items() if k.startswith(("chatterbox_", "tts_"))},
        "load_seconds": {k: round(v, 2) for k, v in load_seconds.items()},
        "ollama_model": args.model,
        "ollama_preload_error": ollama_error,
        "gpu_memory_mb": {
            "baseline": baseline_mb,
            "after_load": loaded_mb,
            "peak": peak_mb,
            "stack_after_load": loaded_mb - baseline_mb if loaded_mb is not None and baseline_mb is not None else None,
            "stack_peak": peak_mb - baseline_mb if peak_mb is not None and baseline_mb is not None else None,
        },
        "lines": {
            "count": len(line_results),
            "errors": sum(1 for r in results if r["kind"] == "line" and r["error"]),
            "voice_fallbacks": sum(1 for r in results if r["kind"] == "line" and r["voice_fallback"]),
            "synth_s": stats([r["synth_s"] for r in line_results]),
            "rtf": stats([r["rtf"] for r in line_results if r["rtf"] is not None]),
            "stt_s": stats([r["stt_s"] for r in line_results]),
            "wer": stats([r["wer"] for r in line_results if r["wer"] is not None]),
            "worst_wer": sorted(
                ({"id": r["id"], "wer": r["wer"], "heard": r["heard"]} for r in line_results if r["wer"]),
                key=lambda item: item["wer"], reverse=True,
            )[:5],
        },
    }
    if turn_results:
        summary["turns"] = {
            "count": len(turn_results),
            "sources": {s: sum(1 for r in turn_results if r["source"] == s) for s in sorted({r["source"] for r in turn_results})},
            "ai_s": stats([r["ai_s"] for r in turn_results]),
            "voice_s": stats([r["voice_s"] for r in turn_results]),
            "total_s": stats([r["total_s"] for r in turn_results]),
        }

    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for record in results:
            handle.write(json.dumps(record) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    print(f"Voice: {voice_label}  |  GPU: {summary['gpu'].get('name', 'unknown')}")
    print(f"Load: {summary['load_seconds']}")
    print(f"GPU memory (MB): {summary['gpu_memory_mb']}")
    print(f"Lines: {summary['lines']['count']} ok, {summary['lines']['errors']} errors, {summary['lines']['voice_fallbacks']} voice fallbacks")
    for key in ("synth_s", "rtf", "stt_s", "wer"):
        print(f"  {key:<7} {summary['lines'][key]}")
    if turn_results:
        print(f"Turns: {summary['turns']}")
    print(f"Saved to {out_dir}")
    return 1 if summary["lines"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
