"""Time streamed replies and check VRAM against the show PC's two GPUs.

On the show PC (2060 text + 3070 voice) run it plainly to measure the real
thing. On a single bigger GPU add --simulate-show-pc to cap the voice at 8 GB
and slow both models to roughly 2060/3070 speed.

    .\\run_stream_check.ps1 --simulate-show-pc
    .\\run_stream_check.ps1 --mute "Why do cats purr?" "Tell me a story."
"""

from __future__ import annotations

import argparse
import json
import socket
import statistics
import time
from pathlib import Path

from machine_paths import MACHINE
from pipeline import warm_ollama_model
from streaming_speech import SHOW_PC, StreamSettings, ollama_vram_gb, speak_streamed_turn
from tts_chatterbox import (
    UNCAPPED_VOICE_OVERHEAD_GB,
    create_voice,
    describe_voice,
    limit_voice_vram,
    voice_peak_vram_gb,
)


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "audio_config.json"
# Open-ended questions the show bank does not answer, so they reach the model.
DEFAULT_QUESTIONS = (
    "How do I start learning to carve wood?",
    "Why do cats purr?",
    "Tell me a story about a lost button.",
    "What would you do with a pet dragon?",
    "How does a pulley lift heavy things?",
    "Tell me something funny about Geppetto.",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure clause-by-clause speech latency and VRAM use.")
    parser.add_argument("questions", nargs="*", help="Questions to ask (defaults to a built-in set).")
    parser.add_argument("--model", default="pinocchio-fast", help="Local Ollama model.")
    parser.add_argument("--simulate-show-pc", action="store_true", help="Mimic the 2060 + 3070 show PC on one GPU.")
    parser.add_argument("--mute", action="store_true", help="Do not play audio (timings are still computed).")
    parser.add_argument("--first-chunk-words", type=int, help="Override stream_first_chunk_words.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if args.first_chunk_words is not None:
        config["stream_first_chunk_words"] = args.first_chunk_words
    settings = StreamSettings.from_config(config, args.simulate_show_pc, play=not args.mute)
    if args.simulate_show_pc:
        cap = limit_voice_vram(SHOW_PC["voice_vram_gb"])
        print(
            f"Simulating show PC: voice PyTorch cap {cap:.1f} GB, "
            f"text x{settings.text_slowdown:g} slower, voice x{settings.voice_slowdown:g} slower."
        )

    print("Loading the voice...")
    voice = create_voice(config)
    print(f"Voice: {describe_voice(voice)}")
    print(f"Loading {args.model}...")
    warm_ollama_model(args.model)

    out_dir = MACHINE.runtime / "stream_checks" / time.strftime("%Y%m%d-%H%M%S")
    results = []
    for turn, question in enumerate(args.questions or DEFAULT_QUESTIONS, start=1):
        result = speak_streamed_turn(
            question, turn, args.model, 12.0, None, voice, settings, wav_path=out_dir / f"turn_{turn:02d}.wav"
        )
        report = result.report
        print(f"\nQ{turn}: {question}")
        print(f"  [{result.source}] {result.packet['spoken_text']}")
        print(
            f"  first text {fmt(report.first_text_s)} | text done {fmt(report.text_done_s)} | "
            f"first audio {fmt(report.first_audio_s)} | speech ends {fmt(report.speech_end_s)} | "
            f"gaps {report.gap_total_s:.2f}s"
        )
        for chunk in report.chunks:
            gap = f"  GAP {chunk['gap_s']:.2f}s" if chunk["gap_s"] else ""
            print(f"    {chunk['synth_s']:5.2f}s synth -> {chunk['audio_s']:5.2f}s audio  {chunk['text']!r}{gap}")
        for error in report.errors:
            print(f"  ! {error}")
        results.append({"question": question, "source": result.source, "packet": result.packet, **report.as_dict()})

    first_audio = [r["first_audio_s"] for r in results if r["first_audio_s"] is not None]
    gaps = [r["gap_total_s"] for r in results]
    text_gb = ollama_vram_gb(args.model)
    voice_gb = voice_peak_vram_gb() + UNCAPPED_VOICE_OVERHEAD_GB
    summary = {
        "computer": socket.gethostname(),
        "model": args.model,
        "simulate_show_pc": args.simulate_show_pc,
        "settings": settings.__dict__,
        "first_audio_s": {"median": median(first_audio), "max": max(first_audio, default=None)},
        "gap_total_s": {"median": median(gaps), "max": max(gaps, default=None)},
        "vram_gb": {"text": text_gb, "voice_estimate": round(voice_gb, 2)},
        "turns": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\nSummary")
    print(f"  first audio: median {fmt(summary['first_audio_s']['median'])}, worst {fmt(summary['first_audio_s']['max'])}")
    print(f"  gaps per reply: median {fmt(summary['gap_total_s']['median'])}, worst {fmt(summary['gap_total_s']['max'])}")
    print(f"  text VRAM:  {fmt_gb(text_gb)} of {SHOW_PC['text_vram_gb']:g} GB (2060)")
    print(
        f"  voice VRAM: ~{voice_gb:.1f} GB of {SHOW_PC['voice_vram_gb']:g} GB (3070) "
        f"incl. {UNCAPPED_VOICE_OVERHEAD_GB:g} GB CUDA/Whisper allowance"
    )
    print(f"  saved: {out_dir}")
    return 0


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 3) if values else None


def fmt(seconds: float | None) -> str:
    return "-" if seconds is None else f"{seconds:.2f}s"


def fmt_gb(value: float | None) -> str:
    return "not loaded" if value is None else f"{value:.1f} GB"


if __name__ == "__main__":
    raise SystemExit(main())
