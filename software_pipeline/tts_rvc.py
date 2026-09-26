"""Pinocchio character voice: Kokoro speech converted through the trained RVC model.

RVC lives in its own Python 3.12 environment on Z:, so it runs as a persistent
worker process (rvc_worker.py) that loads the model once. If the worker is
missing or a conversion fails, the Kokoro audio is used unchanged so the show
keeps talking.
"""

from __future__ import annotations

import atexit
import json
import queue
import shutil
import subprocess
import threading
from pathlib import Path
from typing import IO, Any

from machine_paths import MACHINE
from tts_kokoro import KokoroVoice


ROOT = Path(__file__).resolve().parent
WORKER_PATH = ROOT / "rvc_worker.py"
STARTUP_TIMEOUT_SECONDS = 180.0
CONVERT_TIMEOUT_SECONDS = 60.0


def last_line(text: object) -> str:
    """Condense a worker traceback to the line that names the problem."""
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    return lines[-1] if lines else "unknown RVC error"


class RvcWorker:
    """Owns one rvc_worker.py process and exchanges one JSON line per request."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.rvc_root = MACHINE.rvc
        self.python = MACHINE.rvc_python
        self.model = str(config["rvc_model"])
        # The index is relative to the RVC folder so one config works on every computer.
        index = str(config.get("rvc_index") or "")
        self.index = str(self.rvc_root / index) if index else ""
        self.log_path = MACHINE.runtime / str(config.get("rvc_log_file", "rvc_worker.log"))
        self.settings = {
            "pitch": int(config.get("rvc_pitch", 0)),
            "f0_method": str(config.get("rvc_f0_method", "rmvpe")),
            "index_rate": float(config.get("rvc_index_rate", 0.75)),
            "rms_mix_rate": float(config.get("rvc_rms_mix_rate", 0.25)),
            "protect": float(config.get("rvc_protect", 0.33)),
        }
        self.process: subprocess.Popen[str] | None = None
        self.replies: queue.Queue[str | None] = queue.Queue()
        self.device = ""
        atexit.register(self.stop)

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        if not self.python.is_file():
            raise RuntimeError(f"RVC Python not found: {self.python}")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log:
            self.process = subprocess.Popen(
                [
                    str(self.python), "-u", str(WORKER_PATH),
                    "--rvc-root", str(self.rvc_root),
                    "--model", self.model,
                    "--index", self.index,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=log,
                text=True,
                encoding="utf-8",
                cwd=str(self.rvc_root),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        self.replies = queue.Queue()
        threading.Thread(
            target=self._read_replies, args=(self.process.stdout, self.replies), daemon=True
        ).start()
        ready = self._wait_for_reply(STARTUP_TIMEOUT_SECONDS)
        if not ready.get("ok"):
            self.stop()
            raise RuntimeError(f"RVC model failed to load: {last_line(ready.get('error'))}")
        self.device = str(ready.get("device", ""))

    def convert(self, input_path: Path, output_path: Path) -> float:
        """Convert one WAV and return the worker's conversion time in seconds."""
        if not self.running:
            self.start()
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("RVC worker is not running.")
        request = {"input": str(input_path), "output": str(output_path), **self.settings}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        reply = self._wait_for_reply(CONVERT_TIMEOUT_SECONDS)
        if not reply.get("ok"):
            raise RuntimeError(last_line(reply.get("error")))
        return float(reply.get("seconds", 0.0))

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is None or process.poll() is not None:
            return
        try:
            if process.stdin:
                process.stdin.write(json.dumps({"command": "quit"}) + "\n")
                process.stdin.flush()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()

    @staticmethod
    def _read_replies(stream: IO[str], replies: queue.Queue[str | None]) -> None:
        for line in stream:
            replies.put(line)
        replies.put(None)

    def _wait_for_reply(self, timeout: float) -> dict[str, Any]:
        try:
            line = self.replies.get(timeout=timeout)
        except queue.Empty:
            self.stop()
            raise TimeoutError(f"RVC did not answer within {timeout:.0f} seconds.") from None
        if line is None:
            self.stop()
            raise RuntimeError(f"RVC worker exited unexpectedly; see {self.log_path}")
        return json.loads(line)


class RvcVoice:
    """Kokoro speech converted to the trained Pinocchio voice, with Kokoro fallback."""

    def __init__(self, base: KokoroVoice, worker: RvcWorker) -> None:
        self.base = base
        self.worker = worker
        self.last_error: str | None = None
        self.last_rvc_seconds = 0.0

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        kokoro_path = output_path.with_name(f"{output_path.stem}_kokoro{output_path.suffix}")
        self.base.synthesize_to_wav(text, kokoro_path)
        self.last_error = None
        try:
            self.last_rvc_seconds = self.worker.convert(kokoro_path, output_path)
        except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
            self.last_error = f"Pinocchio voice unavailable, used Kokoro instead: {exc}"
            self.last_rvc_seconds = 0.0
            shutil.copyfile(kokoro_path, output_path)


VoiceEngine = KokoroVoice | RvcVoice


def create_voice(config: dict[str, Any]) -> VoiceEngine:
    """Build the configured voice; RVC problems at startup fall back to plain Kokoro."""
    base = KokoroVoice.from_config(config)
    if not config.get("rvc_enabled"):
        return base
    worker = RvcWorker(config)
    try:
        worker.start()
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        print(f"[RVC voice disabled for this session, using Kokoro: {exc}]", flush=True)
        return base
    return RvcVoice(base, worker)


def describe_voice(voice: VoiceEngine) -> str:
    if isinstance(voice, RvcVoice):
        return f"Kokoro {voice.base.voice} + RVC {Path(voice.worker.model).stem} ({voice.worker.device})"
    return f"Kokoro {voice.voice}"
