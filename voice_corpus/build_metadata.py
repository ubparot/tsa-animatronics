#!/usr/bin/env python3
"""Validate a recorded corpus and emit LJSpeech-format metadata.csv for Piper.

Usage:
    python build_metadata.py                    # validate + write metadata.csv
    python build_metadata.py --check            # validate only, write nothing

Expects:
    prompts_character.txt        id|text lines, '#' comments ignored
    prompts_arctic.txt           same format (optional)
    wavs/<id>.wav                one recording per prompt id
"""

import argparse
import sys
import wave
from pathlib import Path

HERE = Path(__file__).parent
WAVS = HERE / "wavs"

TARGET_RATE = 22050
TARGET_CHANNELS = 1
TARGET_WIDTH = 2  # bytes, i.e. 16-bit

# Flag clips outside these bounds as likely mistakes (bad trim, dead take).
MIN_SEC = 0.6
MAX_SEC = 22.0


def load_prompts():
    """Return [(id, text)] from every prompts_*.txt in this directory."""
    prompts = []
    seen = set()
    for path in sorted(HERE.glob("prompts_*.txt")):
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                print(f"  ! {path.name}:{lineno} has no '|' separator, skipped")
                continue
            pid, text = line.split("|", 1)
            pid, text = pid.strip(), text.strip()
            if pid in seen:
                print(f"  ! duplicate id {pid} in {path.name}:{lineno}, skipped")
                continue
            seen.add(pid)
            prompts.append((pid, text))
    return prompts


def probe(path):
    """Return (seconds, rate, channels, sampwidth) or None if unreadable."""
    try:
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return (frames / rate if rate else 0.0,
                    rate, w.getnchannels(), w.getsampwidth())
    except (wave.Error, EOFError, OSError) as exc:
        print(f"  ! cannot read {path.name}: {exc}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="validate only, do not write metadata.csv")
    args = ap.parse_args()

    prompts = load_prompts()
    if not prompts:
        sys.exit("No prompts found. Expected prompts_*.txt next to this script.")
    print(f"Loaded {len(prompts)} prompts")

    if not WAVS.is_dir():
        sys.exit(f"Missing directory: {WAVS}")

    rows = []
    missing = []
    total_sec = 0.0
    format_problems = []
    length_outliers = []

    for pid, text in prompts:
        path = WAVS / f"{pid}.wav"
        if not path.is_file():
            missing.append(pid)
            continue

        info = probe(path)
        if info is None:
            continue
        seconds, rate, channels, width = info

        if (rate, channels, width) != (TARGET_RATE, TARGET_CHANNELS, TARGET_WIDTH):
            format_problems.append(
                f"{pid}: {rate} Hz, {channels} ch, {width * 8}-bit")
        if not MIN_SEC <= seconds <= MAX_SEC:
            length_outliers.append(f"{pid}: {seconds:.1f}s")

        total_sec += seconds
        rows.append((pid, text))

    recorded = {pid for pid, _ in prompts} & {
        p.stem for p in WAVS.glob("*.wav")}
    orphans = sorted({p.stem for p in WAVS.glob("*.wav")} - recorded)

    print(f"\nRecorded : {len(rows)}")
    print(f"Missing  : {len(missing)}")
    print(f"Duration : {total_sec / 60:.1f} min")
    if rows:
        print(f"Mean clip: {total_sec / len(rows):.1f}s")

    if missing:
        head = ", ".join(missing[:12])
        more = f" (+{len(missing) - 12} more)" if len(missing) > 12 else ""
        print(f"\nNot yet recorded: {head}{more}")

    if orphans:
        print(f"\nWAVs with no matching prompt ({len(orphans)}): "
              + ", ".join(orphans[:12]))

    if format_problems:
        print(f"\nFormat mismatches — want {TARGET_RATE} Hz mono 16-bit "
              f"({len(format_problems)}):")
        for line in format_problems[:12]:
            print(f"  {line}")

    if length_outliers:
        print(f"\nLength outliers, check trimming ({len(length_outliers)}):")
        for line in length_outliers[:12]:
            print(f"  {line}")

    if total_sec < 45 * 60:
        print(f"\n>> {45 - total_sec / 60:.0f} more minutes to reach the "
              f"45-minute fine-tuning floor.")
    else:
        print("\n>> Enough audio to fine-tune.")

    if args.check:
        return

    out = HERE / "metadata.csv"
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for pid, text in rows:
            fh.write(f"{pid}|{text}|{text}\n")
    print(f"\nWrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
