"""Local Chatterbox voice-cloning adapter for the Pinocchio show pipeline."""

from __future__ import annotations

import random
import threading
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch
from chatterbox.tts_turbo import ChatterboxTurboTTS

from machine_paths import MACHINE


class ChatterboxVoice:
    """One preloaded Chatterbox Turbo model conditioned on Pinocchio's voice."""

    def __init__(self, config: dict[str, Any]) -> None:
        requested_device = str(config.get("chatterbox_device", "cuda")).lower()
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Chatterbox is configured for CUDA, but PyTorch cannot see the GPU.")
        if requested_device not in {"cuda", "cpu"}:
            raise ValueError("chatterbox_device must be 'cuda' or 'cpu'.")

        reference = Path(str(config["chatterbox_reference"]))
        self.reference_path = reference if reference.is_absolute() else MACHINE.voice_training / reference
        if not self.reference_path.is_file():
            raise FileNotFoundError(f"Chatterbox reference audio not found: {self.reference_path}")
        reference_info = sf.info(str(self.reference_path))
        if reference_info.duration < 5.0:
            raise ValueError(
                f"Chatterbox reference audio is only {reference_info.duration:.1f}s; use at least 5 seconds."
            )

        self.device = requested_device
        self.temperature = _bounded(config, "chatterbox_temperature", 0.80, 0.05, 5.0)
        self.top_p = _bounded(config, "chatterbox_top_p", 0.95, 0.0, 1.0)
        self.top_k = int(config.get("chatterbox_top_k", 1000))
        if not 1 <= self.top_k <= 5000:
            raise ValueError("chatterbox_top_k must be between 1 and 5000.")
        self.repetition_penalty = _bounded(config, "chatterbox_repetition_penalty", 1.2, 1.0, 2.0)
        self.seed = int(config.get("chatterbox_seed", 20260920))
        self.last_error: str | None = None
        self._lock = threading.Lock()

        self.model = ChatterboxTurboTTS.from_pretrained(device=self.device)
        # Voice encoding is relatively expensive. Reuse it for every show line,
        # while generate() may still update the lightweight exaggeration value.
        self.model.prepare_conditionals(str(self.reference_path))
        self._conditionals: dict[str, Any] = {
            str(self.reference_path.resolve()).lower(): self.model.conds,
        }
        self.sample_rate = int(self.model.sr)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ChatterboxVoice":
        if str(config.get("tts_engine", "")).lower() != "chatterbox":
            raise ValueError("audio_config.json must set tts_engine to 'chatterbox'.")
        return cls(config)

    def synthesize_to_wav(self, text: str, output_path: Path) -> None:
        self.synthesize_variant_to_wav(text, output_path, {})

    def synthesize_variant_to_wav(
        self,
        text: str,
        output_path: Path,
        settings: dict[str, Any],
    ) -> None:
        """Generate one audition variant without changing the live defaults."""
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Chatterbox cannot synthesize empty text.")
        reference = Path(str(settings.get("reference_path", self.reference_path)))
        if not reference.is_absolute():
            reference = MACHINE.voice_training / reference
        if not reference.is_file():
            raise FileNotFoundError(f"Chatterbox reference audio not found: {reference}")
        temperature = _bounded(settings, "temperature", self.temperature, 0.05, 5.0)
        top_p = _bounded(settings, "top_p", self.top_p, 0.0, 1.0)
        top_k = int(settings.get("top_k", self.top_k))
        repetition_penalty = _bounded(
            settings, "repetition_penalty", self.repetition_penalty, 1.0, 2.0
        )
        seed = int(settings.get("seed", self.seed))
        if not 1 <= top_k <= 5000:
            raise ValueError("top_k must be between 1 and 5000.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._activate_reference(reference)
            self._set_seed(seed)
            self.last_error = None
            waveform = self.model.generate(
                clean_text,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
            )
        samples = waveform.squeeze().detach().float().cpu().numpy()
        if samples.size == 0 or not np.isfinite(samples).all():
            raise RuntimeError("Chatterbox produced invalid audio.")
        sf.write(str(output_path), samples, self.sample_rate, subtype="PCM_16")

    def apply_settings(self, settings: dict[str, Any]) -> None:
        """Make a rated variant the default for later live generations."""
        reference = Path(str(settings.get("reference_path", self.reference_path)))
        if not reference.is_absolute():
            reference = MACHINE.voice_training / reference
        temperature = _bounded(settings, "temperature", self.temperature, 0.05, 5.0)
        top_p = _bounded(settings, "top_p", self.top_p, 0.0, 1.0)
        top_k = int(settings.get("top_k", self.top_k))
        repetition_penalty = _bounded(
            settings, "repetition_penalty", self.repetition_penalty, 1.0, 2.0
        )
        seed = int(settings.get("seed", self.seed))
        if not reference.is_file() or not 1 <= top_k <= 5000:
            raise ValueError("The selected Chatterbox settings are invalid.")
        with self._lock:
            self._activate_reference(reference)
            self.reference_path = reference
            self.temperature = temperature
            self.top_p = top_p
            self.top_k = top_k
            self.repetition_penalty = repetition_penalty
            self.seed = seed

    def _activate_reference(self, reference: Path) -> None:
        key = str(reference.resolve()).lower()
        conditionals = self._conditionals.get(key)
        if conditionals is None:
            self.model.prepare_conditionals(str(reference))
            conditionals = self.model.conds
            self._conditionals[key] = conditionals
        else:
            self.model.conds = conditionals

    @staticmethod
    def _set_seed(seed: int) -> None:
        if seed <= 0:
            return
        random.seed(seed)
        np.random.seed(seed % (2**32 - 1))
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)


VoiceEngine = ChatterboxVoice


def create_voice(config: dict[str, Any]) -> VoiceEngine:
    return ChatterboxVoice.from_config(config)


def describe_voice(voice: VoiceEngine) -> str:
    return (
        f"Chatterbox Turbo | {voice.reference_path.stem} | {voice.device} | "
        f"temperature {voice.temperature:.2f} | top-p {voice.top_p:.2f}"
    )


def _bounded(config: dict[str, Any], key: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(config.get(key, default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}.")
    return value
