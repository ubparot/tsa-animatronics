"""Push-to-talk, offline voice interface for the Pinocchio show pipeline."""

from __future__ import annotations

import argparse
import json
import os
import time
import wave
import winsound
from pathlib import Path
from typing import Any

from cuda_runtime import enable_torch_cuda_dlls

# Must happen before CTranslate2 is imported through faster-whisper.
enable_torch_cuda_dlls()

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from machine_paths import MACHINE
from pipeline import LOG_PATH, VALID_TAGS, apply_simulation, get_response, motion
from tts_chatterbox import VoiceEngine, create_voice, describe_voice


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "audio_config.json"
VOICE_LOG_PATH = ROOT / "voice_runs.jsonl"
RUNTIME_ROOT = MACHINE.runtime
RECORDING_PATH = RUNTIME_ROOT / "last_question.wav"
SPEECH_PATH = RUNTIME_ROOT / "last_response.wav"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def record_question(config: dict[str, Any]) -> Path:
    """Record after Enter, stopping when the speaker is quiet for a set period."""
    sample_rate = int(config["sample_rate"])
    channels = int(config["channels"])
    block_size = 1024
    block_seconds = block_size / sample_rate
    threshold = float(config["speech_rms_threshold"])
    max_blocks = int(float(config["max_record_seconds"]) / block_seconds)
    start_blocks = int(float(config["start_timeout_seconds"]) / block_seconds)
    end_silence_blocks = int(float(config["end_silence_seconds"]) / block_seconds)
    selected_device = config.get("input_device")

    print("Listening now. Speak clearly; recording stops after a short pause.")
    pre_roll: list[np.ndarray] = []
    recorded: list[np.ndarray] = []
    speech_started = False
    quiet_blocks = 0
    with sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        blocksize=block_size,
        device=selected_device,
    ) as stream:
        for index in range(max_blocks):
            samples, overflowed = stream.read(block_size)
            if overflowed:
                print("[microphone overflow detected]", flush=True)
            mono = samples[:, 0].copy()
            rms = float(np.sqrt(np.mean(np.square(mono))))
            if not speech_started:
                pre_roll.append(mono)
                pre_roll = pre_roll[-4:]
                if rms >= threshold:
                    speech_started = True
                    recorded.extend(pre_roll)
                    quiet_blocks = 0
                elif index >= start_blocks:
                    break
                continue

            recorded.append(mono)
            quiet_blocks = quiet_blocks + 1 if rms < threshold else 0
            if quiet_blocks >= end_silence_blocks:
                break

    if not speech_started or not recorded:
        raise RuntimeError("No speech was detected. Move closer to the microphone and try again.")

    audio = np.concatenate(recorded)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    RECORDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(RECORDING_PATH), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return RECORDING_PATH


def transcribe(stt: WhisperModel, recording: Path) -> str:
    segments, _info = stt.transcribe(
        str(recording),
        language="en",
        beam_size=3,
        vad_filter=True,
        condition_on_previous_text=False,
        without_timestamps=True,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def reprompt_packet() -> dict[str, Any]:
    return {
        "spoken_text": "I did not catch that. Could you please ask me again?",
        "truth_tag": "TRUTH",
        "emotion_intensity": 0.25,
        "source_id": "speech_reprompt",
        "motion": [motion("nose", 0.0, 0.6, 500), motion("head", 0.35, 0.3, 500)],
        "next_state": "SPEAK_TRUTH",
    }


def speak(voice: VoiceEngine, text: str, output_path: Path, mute: bool) -> None:
    voice.synthesize_to_wav(text, output_path)
    voice_error = getattr(voice, "last_error", None)
    if voice_error:
        print(f"[{voice_error}]", flush=True)
    if not mute:
        winsound.PlaySound(str(output_path), winsound.SND_FILENAME)


def list_devices() -> int:
    print(sd.query_devices())
    return 0


def main() -> int:
    config = load_config()
    parser = argparse.ArgumentParser(description="Run offline speech recognition, AI response, and speech output.")
    parser.add_argument("--model", default="pinocchio-fast", help="Local Ollama model")
    parser.add_argument("--force-tag", choices=sorted(VALID_TAGS), help="Force a predictable show outcome.")
    parser.add_argument("--mute", action="store_true", help="Create the WAV response without playing it.")
    parser.add_argument("--list-devices", action="store_true", help="List microphone and speaker device IDs.")
    parser.add_argument("--stt-device", default=config["whisper_device"], choices=("cuda", "cpu"))
    parser.add_argument("--stt-compute-type", default=config["whisper_compute_type"])
    args = parser.parse_args()

    if args.list_devices:
        return list_devices()

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    print("Loading offline speech recognition model. This only takes a moment after first use.")
    stt = WhisperModel(
        config["whisper_model"],
        device=args.stt_device,
        compute_type=args.stt_compute_type,
        download_root=str(RUNTIME_ROOT / "whisper"),
    )
    voice = create_voice(config)
    print(f"Voice: {describe_voice(voice)}")

    print("Voice pipeline ready. Press Enter to record, or type q then Enter to quit.")
    turn = 0
    while True:
        try:
            command = input("\nEnter=record | q=quit > ").strip().lower()
        except EOFError:
            # Allows a clean exit when the program is launched without an interactive console.
            break
        if command in {"q", "quit", "exit"}:
            break
        turn += 1
        try:
            recording = record_question(config)
            question = transcribe(stt, recording)
            if not question:
                raise RuntimeError("Speech was not clear enough to transcribe.")
            print(f"Heard: {question}")
            packet, source = get_response(question, turn, args.model, 8.0, args.force_tag)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"[speech fallback: {exc}]")
            question = ""
            packet = reprompt_packet()
            source = "speech_fallback"

        print(f"\nSource: {source}")
        print(json.dumps(packet, indent=2))
        apply_simulation(packet)
        speak(voice, packet["spoken_text"], SPEECH_PATH, args.mute)
        record = {
            "time": time.time(),
            "transcript": question,
            "source": source,
            "packet": packet,
            "recording": str(RECORDING_PATH),
            "speech": str(SPEECH_PATH),
        }
        with VOICE_LOG_PATH.open("a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
