"""Generate every planned clip, one engine per run so each gets the whole GPU.

    python generate.py --engine turbo
    python generate.py --engine original
    python generate.py --engine rvc

Existing clips are skipped, so a run can be repeated after a crash. Each clip
gets one line in data/generation_log.jsonl (device, length, errors).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HOME", "E:/PinocchioAudio/hf-cache")
os.environ.setdefault("HF_HUB_CACHE", "E:/PinocchioAudio/hf-cache/hub")

import numpy as np
import soundfile as sf
import torch

from design import AUDIO_ROOT, CLIPS, DATA, VOICE_TRAINING, read_csv

PIPELINE = Path(__file__).resolve().parents[1] / "software_pipeline"
ORIGINAL_SNAPSHOT = AUDIO_ROOT / "hf-cache/hub/models--ResembleAI--chatterbox/snapshots/5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
RVC_ROOT = Path("Z:/PinocchioRVC")
RVC_PYTHON = RVC_ROOT / "venv/Scripts/python.exe"
RVC_INDEX = RVC_ROOT / "logs/pinocchio_voice/added_IVF872_Flat_nprobe_1_pinocchio_voice_v2.index"
KOKORO_VOICE = "am_puck"
LOG = DATA / "generation_log.jsonl"


SAFETENSOR_DTYPES = {
    "F32": torch.float32, "F16": torch.float16, "BF16": torch.bfloat16, "I64": torch.int64,
    "I32": torch.int32, "I16": torch.int16, "I8": torch.int8, "U8": torch.uint8, "BOOL": torch.bool,
}


def streamed_load_file(filename, device="cuda") -> dict[str, torch.Tensor]:
    """safetensors.load_file without memory-mapping: one tensor at a time to the GPU."""
    tensors = {}
    with open(filename, "rb") as f:
        header_len = int.from_bytes(f.read(8), "little")
        header = json.loads(f.read(header_len))
        base = 8 + header_len
        for name, meta in header.items():
            if name == "__metadata__":
                continue
            start, end = meta["data_offsets"]
            f.seek(base + start)
            raw = bytearray(f.read(end - start))
            cpu = torch.frombuffer(raw, dtype=SAFETENSOR_DTYPES[meta["dtype"]]) if raw else \
                torch.empty(0, dtype=SAFETENSOR_DTYPES[meta["dtype"]])
            tensors[name] = cpu.reshape(meta["shape"]).to(device)
    return tensors


class gpu_first_load:
    """Build models straight on the GPU so loading needs little system RAM.

    This PC's page file cannot grow (C: is nearly full), and the stock loaders
    stage every weight in RAM before moving it to the GPU.
    """

    def __enter__(self):
        import chatterbox.tts as tts
        import chatterbox.tts_turbo as tts_turbo
        from safetensors.torch import load_file

        self._modules = (tts, tts_turbo)
        self._load_file = load_file
        for module in self._modules:
            module.load_file = streamed_load_file
        self._device = torch.device("cuda")
        self._device.__enter__()

    def __exit__(self, *exc):
        self._device.__exit__(*exc)
        for module in self._modules:
            module.load_file = self._load_file


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def log(entry: dict) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def jobs_for(engine_name: str) -> list[tuple[dict, dict, dict]]:
    settings = {s["SettingID"]: s for s in read_csv(DATA / "settings.csv")}
    prompts = {p["PromptID"]: p for p in read_csv(DATA / "prompts.csv")}
    jobs = []
    for clip in read_csv(DATA / "plan.csv"):
        setting = settings[clip["SettingID"]]
        if setting["Engine"] == engine_name and not (CLIPS / clip["FileName"]).is_file():
            jobs.append((clip, setting, prompts[clip["PromptID"]]))
    return jobs


def save(clip: dict, samples: np.ndarray, sr: int, device: str, started: float, extra: dict | None = None) -> None:
    CLIPS.mkdir(parents=True, exist_ok=True)
    sf.write(str(CLIPS / clip["FileName"]), samples, sr, subtype="PCM_16")
    log({"ClipID": clip["ClipID"], "ok": True, "device": device, "sr": sr,
         "duration": round(len(samples) / sr, 3), "seconds": round(time.perf_counter() - started, 2),
         **(extra or {})})


def run_turbo() -> None:
    sys.path.insert(0, str(PIPELINE))
    from tts_chatterbox import ChatterboxVoice

    jobs = jobs_for("Chatterbox Turbo")
    if not jobs:
        return
    with gpu_first_load():
        voice = ChatterboxVoice({"chatterbox_reference": "wavs/chr_0200.wav", "chatterbox_cuda_graph": False})
    for clip, s, p in jobs:
        started = time.perf_counter()
        samples = voice._generate(p["PromptText"], {
            "reference_path": str(VOICE_TRAINING / "wavs" / s["ReferenceClip"]),
            "temperature": float(s["Temperature"]), "top_p": float(s["TopP"]),
            "top_k": int(float(s["TopK"])), "repetition_penalty": float(s["RepetitionPenalty"]),
            "seed": int(clip["Seed"]),
        })
        save(clip, samples, voice.sample_rate, "cuda", started)
        print(clip["ClipID"], s["LevelLabel"], p["PromptID"], f"{len(samples) / voice.sample_rate:.1f}s", flush=True)


def run_original(device: str) -> None:
    from chatterbox.tts import ChatterboxTTS

    jobs = jobs_for("Chatterbox (original)")
    if not jobs:
        return
    if device == "cuda":
        with gpu_first_load():
            model = ChatterboxTTS.from_local(ORIGINAL_SNAPSHOT, device)
    else:
        model = ChatterboxTTS.from_local(ORIGINAL_SNAPSHOT, device)
    prepared = None
    for clip, s, p in jobs:
        ref = str(VOICE_TRAINING / "wavs" / s["ReferenceClip"])
        if prepared != ref:
            model.prepare_conditionals(ref, exaggeration=0.5)
            prepared = ref
        started = time.perf_counter()
        set_seed(int(clip["Seed"]))
        wav = model.generate(
            p["PromptText"], temperature=float(s["Temperature"]), top_p=float(s["TopP"]),
            min_p=float(s["MinP"]), repetition_penalty=float(s["RepetitionPenalty"]),
            cfg_weight=max(float(s["CFGWeight"]), 1e-6), exaggeration=float(s["Exaggeration"]),
        )
        samples = wav.squeeze().float().cpu().numpy()
        save(clip, samples, int(model.sr), device, started)
        print(clip["ClipID"], s["LevelLabel"], p["PromptID"], f"{len(samples) / model.sr:.1f}s", flush=True)


def median_f0(paths: list[Path]) -> float:
    import librosa

    values = []
    for path in paths:
        y, sr = librosa.load(str(path), sr=16000)
        f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=600, sr=sr)
        values.extend(f0[voiced & np.isfinite(f0)])
    return float(np.median(values))


def run_rvc() -> None:
    sys.path.insert(0, str(PIPELINE))
    from tts_kokoro import KokoroVoice

    jobs = jobs_for("Kokoro + RVC")
    if not jobs:
        return
    sources = AUDIO_ROOT / "kokoro_sources"
    sources.mkdir(parents=True, exist_ok=True)
    kokoro = KokoroVoice(language="a", voice=KOKORO_VOICE, speed=1.0)
    source_for = {}
    for clip, _s, p in jobs:
        path = sources / f"{p['PromptID']}.wav"
        if not path.is_file():
            kokoro.synthesize_to_wav(p["PromptText"], path)
        source_for[clip["ClipID"]] = path

    # Shift Kokoro's adult voice to the character's register, measured rather than guessed.
    targets = [VOICE_TRAINING / "wavs" / f"chr_{n:04d}.wav" for n in range(196, 211)]
    target_f0 = median_f0([t for t in targets if t.is_file()])
    source_f0 = median_f0(sorted(set(source_for.values())))
    pitch = int(round(12 * np.log2(target_f0 / source_f0)))
    print(f"Kokoro median F0 {source_f0:.0f} Hz, character {target_f0:.0f} Hz -> pitch shift {pitch:+d} semitones")
    (DATA / "rvc_pitch.json").write_text(json.dumps(
        {"source_f0": source_f0, "target_f0": target_f0, "pitch_shift": pitch}, indent=2))

    worker = subprocess.Popen(
        [str(RVC_PYTHON), "-u", str(PIPELINE / "rvc_worker.py"), "--rvc-root", str(RVC_ROOT),
         "--model", "pinocchio_voice.pth", "--index", str(RVC_INDEX)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(AUDIO_ROOT / "rvc_worker.log", "a"),
        text=True, encoding="utf-8", cwd=str(RVC_ROOT))
    ready = json.loads(worker.stdout.readline())
    if not ready.get("ok"):
        raise RuntimeError(ready.get("error"))
    print("RVC worker on", ready["device"])
    for clip, s, p in jobs:
        started = time.perf_counter()
        source = source_for[clip["ClipID"]]
        if s["ConversionStrength"] == "":
            samples, sr = sf.read(str(source), dtype="float32")
            save(clip, samples, sr, "kokoro", started, {"pitch_shift": 0})
            continue
        out = CLIPS / clip["FileName"]
        worker.stdin.write(json.dumps({
            "input": str(source), "output": str(out), "pitch": pitch, "f0_method": "rmvpe",
            "index_rate": float(s["ConversionStrength"]), "rms_mix_rate": float(s["RmsMix"]),
            "protect": float(s["Protect"]),
        }) + "\n")
        worker.stdin.flush()
        reply = json.loads(worker.stdout.readline())
        if not reply.get("ok"):
            log({"ClipID": clip["ClipID"], "ok": False, "error": reply.get("error", "")[-500:]})
            print(clip["ClipID"], "FAILED", reply.get("error", "")[-300:])
            continue
        info = sf.info(str(out))
        log({"ClipID": clip["ClipID"], "ok": True, "device": ready["device"], "sr": info.samplerate,
             "duration": round(info.duration, 3), "seconds": reply["seconds"], "pitch_shift": pitch})
        print(clip["ClipID"], s["LevelLabel"], p["PromptID"], f"{info.duration:.1f}s", flush=True)
    worker.stdin.write(json.dumps({"command": "quit"}) + "\n")
    worker.stdin.flush()
    worker.wait(timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["turbo", "original", "rvc"], required=True)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    {"turbo": run_turbo, "original": lambda: run_original(args.device), "rvc": run_rvc}[args.engine]()
    print("done")
