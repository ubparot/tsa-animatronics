"""Persistent RVC voice-conversion worker for the Pinocchio show pipeline.

This script runs inside the RVC environment (the Python 3.12 venv in the rvc
folder named in machine.json), not the show pipeline's environment. tts_rvc.py starts it once so the model stays
loaded, then sends one JSON request per line on stdin. Each reply is one JSON line
on stdout. RVC's own logging is redirected to stderr so it cannot corrupt replies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import warnings
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve RVC conversions over stdin/stdout.")
    parser.add_argument("--rvc-root", required=True, help="RVC checkout folder (the rvc path in machine.json).")
    parser.add_argument("--model", required=True, help="Model .pth name in assets/weights, or a full path.")
    parser.add_argument("--index", default="", help="Added .index file; empty disables index blending.")
    args = parser.parse_args()

    protocol = sys.stdout
    sys.stdout = sys.stderr

    def reply(payload: dict[str, object]) -> None:
        protocol.write(json.dumps(payload) + "\n")
        protocol.flush()

    root = Path(args.rvc_root).resolve()
    os.chdir(root)
    # Drop this script's folder so the pipeline's modules never shadow RVC's.
    sys.path[:] = [str(root)] + sys.path[1:]
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("index_root", str(root / "logs"))
    os.environ.setdefault("outside_index_root", str(root / "assets" / "indices"))
    os.environ.setdefault("rmvpe_root", str(root / "assets" / "rmvpe"))
    warnings.filterwarnings("ignore", category=FutureWarning)

    try:
        model_path = Path(args.model)
        if not model_path.is_absolute():
            model_path = root / "assets" / "weights" / args.model
        if not model_path.is_file():
            raise FileNotFoundError(f"RVC model not found: {model_path}")
        if args.index and not Path(args.index).is_file():
            raise FileNotFoundError(f"RVC index not found: {args.index}")
        os.environ["weight_root"] = str(model_path.parent)

        import soundfile as sf
        from configs.config import Config
        from infer.vc import modules as vc_modules

        # Config parses sys.argv for WebUI flags; give it a clean argument list.
        worker_argv = sys.argv
        sys.argv = [sys.argv[0]]
        try:
            config = Config()
        finally:
            sys.argv = worker_argv
        vc = vc_modules.VC(config)
        vc.get_vc(model_path.name)
        vc.hubert_model = vc_modules.load_hubert(config)

        # The first conversion also loads RMVPE and warms up CUDA (~14 s), so run
        # it now on a short voiced tone instead of on the first visitor reply.
        import numpy as np

        warmup_path = root / "tmp" / "pinocchio_rvc_warmup.wav"
        warmup_path.parent.mkdir(parents=True, exist_ok=True)
        t = np.arange(16000) / 16000
        tone = 0.3 * sum(np.sin(2 * np.pi * 160 * k * t) / k for k in range(1, 6))
        sf.write(str(warmup_path), tone.astype(np.float32), 16000)
        vc.vc_single(0, str(warmup_path), 0, "rmvpe", args.index, 0.75, 0, 0.25, 0.33)
    except Exception:
        reply({"ok": False, "error": traceback.format_exc()})
        return 1

    reply({"ok": True, "device": str(config.device), "sampleRate": vc.tgt_sr})

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if request.get("command") == "quit":
                break
            started = time.perf_counter()
            status, result = vc.vc_single(
                0,
                str(request["input"]),
                int(request.get("pitch", 0)),
                str(request.get("f0_method", "rmvpe")),
                args.index,
                float(request.get("index_rate", 0.75)),
                0,
                float(request.get("rms_mix_rate", 0.25)),
                float(request.get("protect", 0.33)),
            )
            sample_rate, audio = result if result else (None, None)
            if sample_rate is None or audio is None:
                raise RuntimeError(f"RVC conversion failed: {status}")
            output_path = Path(request["output"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), audio, sample_rate, subtype="PCM_16")
            reply({"ok": True, "output": str(output_path), "seconds": round(time.perf_counter() - started, 2)})
        except Exception:
            reply({"ok": False, "error": traceback.format_exc()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
