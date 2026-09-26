"""Expose PyTorch's bundled CUDA DLLs before loading CTranslate2 on Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path


_DLL_DIRECTORIES: list[object] = []


def enable_torch_cuda_dlls() -> None:
    """Make the CUDA 12/cuDNN 9 DLLs in this virtual environment discoverable.

    The CUDA-enabled PyTorch wheel bundles these runtime files under torch/lib.
    CTranslate2 (used by faster-whisper) needs the directory in the DLL search
    path before it initializes a GPU model.
    """
    venv_root = Path(sys.executable).resolve().parent.parent
    torch_lib = venv_root / "Lib" / "site-packages" / "torch" / "lib"
    if not (torch_lib / "cublas64_12.dll").is_file():
        return
    path = str(torch_lib)
    if path not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        _DLL_DIRECTORIES.append(os.add_dll_directory(path))
