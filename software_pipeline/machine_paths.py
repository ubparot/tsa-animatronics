"""Per-computer folder locations for the Pinocchio pipeline.

Everything that differs between the workshop PC and the show PC lives in
machine.json next to this file. Each entry under "paths" is either absolute or
relative to "root", so a new computer only needs "root" set (see
machine.example.json). machine_paths.ps1 applies the same rules for the
PowerShell launchers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MACHINE_CONFIG_PATH = ROOT / "machine.json"
PATH_KEYS = ("runtime", "rvc", "ollama_exe", "ollama_models", "voice_training")


@dataclass(frozen=True)
class MachinePaths:
    runtime: Path
    rvc: Path
    ollama_exe: Path
    ollama_models: Path
    voice_training: Path

    @property
    def runtime_python(self) -> Path:
        return self.runtime / "venv" / "Scripts" / "python.exe"

    @property
    def rvc_python(self) -> Path:
        return self.rvc / "venv" / "Scripts" / "python.exe"


def load_machine_paths(config_path: Path = MACHINE_CONFIG_PATH) -> MachinePaths:
    if not config_path.is_file():
        raise FileNotFoundError(
            f"{config_path} is missing. Copy machine.example.json to machine.json and set root for this computer."
        )
    # utf-8-sig tolerates the byte-order mark Notepad adds when saving.
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    root = Path(config["root"])

    def resolve(key: str) -> Path:
        value = Path(config["paths"][key])
        return value if value.is_absolute() else root / value

    return MachinePaths(**{key: resolve(key) for key in PATH_KEYS})


MACHINE = load_machine_paths()
