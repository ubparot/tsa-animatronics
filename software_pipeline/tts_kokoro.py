"""Offline Kokoro text-to-speech adapter for the Pinocchio show pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
from kokoro import KModel, KPipeline


class KokoroVoice:
    """One locally cached Kokoro voice, ready to synthesize show dialogue."""

    sample_rate = 24_000

    def __init__(self, language: str, voice: str, speed: float) -> None:
        self.voice = voice
        self.speed = speed
        self.language = language
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline = self._create_pipeline(self.device)

    def _create_pipeline(self, device: str) -> KPipeline:
        if device == "cuda":
            # Kokoro's standard iSTFT path uses complex CUDA operations that fail
            # on this RTX/PyTorch combination. Its non-complex decoder is compatible
            # with the same pretrained weights and keeps the voice on the GPU.
            model = KModel(repo_id="hexgrad/Kokoro-82M", disable_complex=True).to(device).eval()
            return KPipeline(lang_code=self.language, repo_id="hexgrad/Kokoro-82M", model=model)
        return KPipeline(lang_code=self.language, repo_id="hexgrad/Kokoro-82M", device="cpu")

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "KokoroVoice":
        return cls(
            language=str(config["kokoro_language"]),
            voice=str(config["kokoro_voice"]),
            speed=float(config["kokoro_speed"]),
        )

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        """Create a standard 24 kHz PCM WAV without sending text off the computer."""
        try:
            pieces = self._synthesize(text)
        except RuntimeError:
            if self.device != "cuda":
                raise
            # Keep the show available if a future GPU driver/runtime update fails.
            self.device = "cpu"
            self.pipeline = self._create_pipeline(self.device)
            pieces = self._synthesize(text)
        if not pieces:
            raise RuntimeError("Kokoro did not produce any audio for that response.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), np.concatenate(pieces), self.sample_rate, subtype="PCM_16")

    def _synthesize(self, text: str) -> list[np.ndarray]:
        return [
            np.asarray(audio, dtype=np.float32)
            for _graphemes, _phonemes, audio in self.pipeline(
                text.strip(), voice=self.voice, speed=self.speed
            )
        ]
