"""Prepare short voice clips for local character-voice training.

The source clips remain untouched. Converted WAV files, transcripts, and the
review list are written to E: by default so the project does not fill C:.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import wave
from pathlib import Path
from statistics import mean

from cuda_runtime import enable_torch_cuda_dlls

enable_torch_cuda_dlls()

from faster_whisper import WhisperModel  # noqa: E402

from machine_paths import MACHINE  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "audio"
DEFAULT_OUTPUT = MACHINE.voice_training
AUDIO_SUFFIXES = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def convert_to_wav(ffmpeg: str, source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def transcribe(model: WhisperModel, wav_path: Path) -> tuple[str, float | None]:
    segments, _info = model.transcribe(
        str(wav_path),
        language="en",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    rows = list(segments)
    text = " ".join(segment.text.strip() for segment in rows if segment.text.strip())
    confidence = mean(segment.avg_logprob for segment in rows) if rows else None
    return text, confidence


def review_reason(text: str, duration: float, confidence: float | None) -> str:
    if duration < 1.2:
        return "very_short"
    if not text:
        return "no_transcript"
    if len(text.split()) < 2:
        return "too_few_words"
    if confidence is not None and confidence < -1.0:
        return "low_transcription_confidence"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert and transcribe character-voice clips locally.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--whisper-model", default="base.en")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    ffmpeg = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg was not found on PATH.")
    source_files = sorted(
        path for path in args.source.iterdir() if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES
    )
    if not source_files:
        raise FileNotFoundError(f"No audio clips found in {args.source}")

    wav_root = args.output / "wavs"
    args.output.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(
        args.whisper_model,
        device=args.device,
        compute_type=args.compute_type,
        download_root=str(MACHINE.runtime / "whisper"),
    )

    records: list[dict[str, object]] = []
    for index, source in enumerate(source_files, start=1):
        wav_path = wav_root / f"{source.stem}.wav"
        if args.overwrite or not wav_path.is_file():
            convert_to_wav(ffmpeg, source, wav_path)
        duration = wav_duration(wav_path)
        text, confidence = transcribe(model, wav_path)
        record = {
            "file_name": wav_path.name,
            "source": str(source.resolve()),
            "duration_seconds": round(duration, 3),
            "transcript": text,
            "whisper_avg_logprob": round(confidence, 3) if confidence is not None else None,
        }
        record["review_reason"] = review_reason(text, duration, confidence)
        records.append(record)
        print(f"[{index}/{len(source_files)}] {wav_path.name}: {text}")

    manifest_path = args.output / "transcripts.jsonl"
    with manifest_path.open("w", encoding="utf-8") as manifest:
        for record in records:
            manifest.write(json.dumps(record, ensure_ascii=False) + "\n")

    accepted = [record for record in records if not record["review_reason"]]
    with (args.output / "metadata.csv").open("w", encoding="utf-8", newline="") as metadata:
        writer = csv.writer(metadata, delimiter="|")
        for record in accepted:
            writer.writerow((record["file_name"], record["transcript"]))
    with (args.output / "review_needed.csv").open("w", encoding="utf-8", newline="") as review:
        writer = csv.DictWriter(review, fieldnames=list(records[0]), delimiter="|")
        writer.writeheader()
        writer.writerows(record for record in records if record["review_reason"])

    total_seconds = sum(float(record["duration_seconds"]) for record in accepted)
    print(
        json.dumps(
            {
                "input_clips": len(source_files),
                "accepted_clips": len(accepted),
                "review_clips": len(records) - len(accepted),
                "accepted_minutes": round(total_seconds / 60, 2),
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
