"""Download, load, and smoke-test Chatterbox during the one-time setup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tts_chatterbox import create_voice, describe_voice


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((ROOT / "audio_config.json").read_text(encoding="utf-8"))
    voice = create_voice(config)
    voice.synthesize_to_wav("The Pinocchio workshop voice is ready.", args.output)
    print("Chatterbox local voice is ready: " + describe_voice(voice))
    print(f"Warm-up audio: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
