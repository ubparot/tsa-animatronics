"""Describe how each clip *behaves*: tone, pauses, resonance, loudness, breathiness, pacing, words.

These are descriptive measurements of delivery, not quality or speed scores.
Each numeric value also gets a plain-language label (e.g. "breathy", "rushed")
using cut-points from the whole study, so the database reads like field notes.

    python analyze.py   -> data/acoustics.csv, data/generations.csv
"""

from __future__ import annotations

import difflib
import json
import os
import re

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HOME", "E:/PinocchioAudio/hf-cache")

import librosa
import numpy as np

from design import CLIPS, DATA, read_csv, spoken_words, write_csv

SR = 16000
HOP = 160  # 10 ms frames


def syllables(word: str) -> int:
    groups = re.findall(r"[aeiouy]+", word.lower())
    count = len(groups) - (1 if word.lower().endswith("e") and len(groups) > 1 else 0)
    return max(1, count)


def pauses(y: np.ndarray) -> tuple[list[float], float, float]:
    """Silent gaps >= 150 ms inside the speech (leading/trailing silence excluded)."""
    rms = librosa.feature.rms(y=y, frame_length=400, hop_length=HOP)[0]
    db = 20 * np.log10(rms + 1e-9)
    speech = db > (db.max() - 35)
    idx = np.flatnonzero(speech)
    if idx.size == 0:
        return [], 0.0, 0.0
    first, last = idx[0], idx[-1]
    gaps, run = [], 0
    for active in speech[first:last + 1]:
        if not active:
            run += 1
        else:
            if run * HOP / SR >= 0.15:
                gaps.append(run * HOP / SR)
            run = 0
    active_time = (last - first + 1) * HOP / SR
    return gaps, active_time, (first * HOP / SR)


def formants(y: np.ndarray, voiced_mask: np.ndarray) -> tuple[float, float]:
    """Median F1/F2 from LPC roots over voiced frames."""
    frames = librosa.util.frame(librosa.effects.preemphasis(y), frame_length=400, hop_length=HOP)
    n = min(frames.shape[1], voiced_mask.size)
    f1s, f2s = [], []
    window = np.hamming(400)
    for i in np.flatnonzero(voiced_mask[:n])[::3]:
        frame = frames[:, i] * window
        if np.abs(frame).max() < 1e-4:
            continue
        a = librosa.lpc(frame, order=12)
        roots = [r for r in np.roots(a) if np.imag(r) > 0]
        freqs = sorted(np.angle(roots) * SR / (2 * np.pi))
        bw = [-0.5 * (SR / (2 * np.pi)) * np.log(abs(r)) for r in roots]
        cands = [f for f, b in sorted(zip(np.angle(roots) * SR / (2 * np.pi), bw)) if 200 < f < 4000 and b < 400]
        if len(cands) >= 2:
            f1s.append(cands[0])
            f2s.append(cands[1])
    return (float(np.median(f1s)) if f1s else float("nan"), float(np.median(f2s)) if f2s else float("nan"))


def hnr(y: np.ndarray, f0: np.ndarray, voiced: np.ndarray) -> float:
    """Harmonics-to-noise ratio (dB) from the normalized autocorrelation peak at the pitch period.

    Lower values mean more aspiration noise: a breathier or rougher voice.
    """
    values = []
    for i in np.flatnonzero(voiced)[::2]:
        if not np.isfinite(f0[i]):
            continue
        start = i * HOP
        frame = y[start:start + 640]
        if frame.size < 640:
            continue
        frame = frame - frame.mean()
        lag = int(round(SR / f0[i]))
        if lag >= frame.size - 1:
            continue
        ac = np.correlate(frame, frame, "full")[frame.size - 1:]
        if ac[0] <= 0:
            continue
        lo, hi = max(1, int(lag * 0.9)), min(frame.size - 1, int(lag * 1.1) + 1)
        r = float(np.clip(ac[lo:hi].max() / ac[0], 1e-4, 0.9999))
        values.append(10 * np.log10(r / (1 - r)))
    return float(np.median(values)) if values else float("nan")


def contour(f0: np.ndarray, voiced: np.ndarray) -> str:
    pts = f0[voiced & np.isfinite(f0)]
    if pts.size < 10:
        return "too little voicing"
    third = max(1, pts.size // 3)
    start, end = np.median(pts[:third]), np.median(pts[-third:])
    tail = pts[-max(3, pts.size // 6):]
    tail_shift = 12 * np.log2(np.median(tail[-3:]) / np.median(tail[:3]))
    overall = 12 * np.log2(end / start)
    if tail_shift > 2:
        return "rising at end"
    if overall < -2:
        return "falling"
    if overall > 2:
        return "rising"
    return "level"


def word_behaviour(intended: list[str], heard: list[str]) -> tuple[str, str]:
    # Apostrophes and compound spacing ("window sill") are spelling, not speech.
    norm = lambda ws: [re.sub(r"[^a-z0-9]", "", w.lower()) for w in ws if re.sub(r"[^a-z0-9]", "", w.lower())]
    # base.en does not know the name Geppetto; map its usual spellings back.
    heard = re.sub(r"\bto pe[td]al\b|\b\w*p+[ae]t+o\b", "Geppetto", " ".join(heard), flags=re.IGNORECASE).split()
    a, b = norm(intended), norm(heard)
    merged, j = [], 0
    while j < len(b):
        if j + 1 < len(b) and b[j] + b[j + 1] in a and b[j] not in a:
            merged.append(b[j] + b[j + 1])
            j += 2
        else:
            merged.append(b[j])
            j += 1
    b = merged
    notes, codes = [], set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "delete":
            codes.add("dropped words")
            notes.append(f"dropped '{' '.join(a[i1:i2])}'")
        elif op == "insert":
            extra = b[j1:j2]
            if any(w in a for w in extra):
                codes.add("repeated words")
                notes.append(f"repeated '{' '.join(extra)}'")
            elif set(extra) & {"whispering", "sigh", "chuckle", "sarcastic", "fear"}:
                codes.add("read cue aloud")
                notes.append(f"spoke cue '{' '.join(extra)}'")
            else:
                codes.add("added words")
                notes.append(f"added '{' '.join(extra)}'")
        elif op == "replace":
            codes.add("substituted words")
            notes.append(f"'{' '.join(a[i1:i2])}' -> '{' '.join(b[j1:j2])}'")
    if not codes:
        return "faithful", ""
    return "; ".join(sorted(codes)), "; ".join(notes)[:250]


def label(value: float, cuts: tuple[float, float], names: tuple[str, str, str]) -> str:
    if not np.isfinite(value):
        return "n/a"
    return names[0] if value < cuts[0] else names[2] if value > cuts[1] else names[1]


def main() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_pipeline"))
    from cuda_runtime import enable_torch_cuda_dlls

    enable_torch_cuda_dlls()
    from faster_whisper import WhisperModel

    whisper = WhisperModel("base.en", device="cuda", compute_type="float16",
                           download_root="E:/PinocchioAudio/whisper")
    log = {}
    for line in (DATA / "generation_log.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        log[entry["ClipID"]] = entry
    prompts = {p["PromptID"]: p for p in read_csv(DATA / "prompts.csv")}
    plan = read_csv(DATA / "plan.csv")

    acoustics, generations = [], []
    for clip in plan:
        path = CLIPS / clip["FileName"]
        if not path.is_file():
            continue
        full, _ = librosa.load(str(path), sr=SR)
        segments, _ = whisper.transcribe(str(path), language="en", beam_size=5, vad_filter=False,
                                         word_timestamps=True)
        segments = list(segments)
        heard = " ".join(s.text.strip() for s in segments).strip()
        stamps = [w for s in segments for w in (s.words or [])]
        clip_len = full.size / SR
        speech_end = min(clip_len, stamps[-1].end + 0.15) if stamps else clip_len
        # Measure delivery only over the spoken span; what follows the last word
        # is described separately as the ending behaviour.
        y = full[: int(speech_end * SR)]
        tail = full[int(speech_end * SR):]
        trailing = clip_len - speech_end
        speech_rms = float(np.sqrt(np.mean(y**2))) if y.size else 0.0
        tail_rms = float(np.sqrt(np.mean(tail**2))) if tail.size else 0.0
        tail_db = 20 * np.log10((tail_rms + 1e-9) / (speech_rms + 1e-9))
        ending = ("clean stop" if trailing < 0.6 else
                  "trailing silence" if tail_db < -30 else
                  "trailing breath/noise" if tail_db < -15 else "keeps vocalizing after the line")

        f0, voiced, _ = librosa.pyin(y, fmin=70, fmax=650, sr=SR, frame_length=1024, hop_length=HOP)
        rms = librosa.feature.rms(y=y, frame_length=400, hop_length=HOP)[0]
        # pyin calls digital silence "voiced" (at fmax); only trust frames with real energy.
        n = min(f0.size, rms.size)
        f0, voiced = f0[:n], voiced[:n] & (20 * np.log10(rms[:n] + 1e-9) > 20 * np.log10(rms.max() + 1e-9) - 40)
        pts = f0[voiced & np.isfinite(f0)]
        gaps, active, _ = pauses(y)
        loud = 20 * np.log10(rms[rms > rms.max() * 0.05] + 1e-9)
        centroid = librosa.feature.spectral_centroid(y=y, sr=SR, hop_length=HOP)[0]
        f1, f2 = formants(y, voiced)
        prompt = prompts[clip["PromptID"]]
        words = spoken_words(prompt["PromptText"])
        rate = sum(syllables(w) for w in words) / max(active - sum(gaps), 0.3)
        codes, notes = word_behaviour(words, heard.split())

        acoustics.append(dict(
            ClipID=clip["ClipID"],
            MeanPitchHz=round(float(np.mean(pts)), 1) if pts.size else None,
            PitchRangeSemitones=round(float(12 * np.log2(np.percentile(pts, 95) / np.percentile(pts, 5))), 2) if pts.size > 5 else None,
            PitchVariabilitySemitones=round(float(np.std(12 * np.log2(pts / np.median(pts)))), 2) if pts.size > 5 else None,
            IntonationContour=contour(f0, voiced),
            PauseCount=len(gaps),
            LongestPauseSec=round(max(gaps), 2) if gaps else 0.0,
            TotalPauseSec=round(sum(gaps), 2),
            SpeechRateSylPerSec=round(rate, 2),
            F1Hz=round(f1) if np.isfinite(f1) else None,
            F2Hz=round(f2) if np.isfinite(f2) else None,
            SpectralCentroidHz=round(float(np.median(centroid))),
            LoudnessDb=round(float(np.median(loud)), 1),
            LoudnessRangeDb=round(float(np.percentile(loud, 95) - np.percentile(loud, 10)), 1),
            HNRdB=round(hnr(y, f0, voiced), 2),
            VoicedFraction=round(float(np.mean(voiced)), 3),
            TrailingSec=round(trailing, 2),
            EndingBehavior=ending,
        ))
        generations.append(dict(
            ClipID=clip["ClipID"], SettingID=clip["SettingID"], PromptID=clip["PromptID"],
            StudyBlock=clip["StudyBlock"], Seed=int(clip["Seed"]), FileName=clip["FileName"],
            DurationSec=log.get(clip["ClipID"], {}).get("duration"),
            Device=log.get(clip["ClipID"], {}).get("device"),
            IntendedWords=" ".join(words), HeardTranscript=heard,
            WordBehavior=codes, WordBehaviorNotes=notes,
        ))
        print(clip["ClipID"], codes, flush=True)

    # Whisper sometimes hallucinates a repeat of the line. A real repeat makes the
    # clip far longer than usual for that prompt, so keep only repeats that do.
    spans = {}
    for g in generations:
        spans.setdefault(g["PromptID"], []).append(g["DurationSec"] or 0)
    for g in generations:
        if "repeated words" in g["WordBehavior"] and (g["DurationSec"] or 0) < 1.5 * float(np.median(spans[g["PromptID"]])):
            codes = [c for c in g["WordBehavior"].split("; ") if c != "repeated words"] or ["faithful"]
            g["WordBehavior"] = "; ".join(codes)
            notes = [n for n in g["WordBehaviorNotes"].split("; ") if not n.startswith("repeated")]
            g["WordBehaviorNotes"] = "; ".join(notes + ["recognizer repeat discarded (clip is normal length)"])

    # Plain-language labels from study-wide tertiles.
    def cuts(key):
        vals = np.array([a[key] for a in acoustics if a[key] is not None and np.isfinite(a[key])])
        return tuple(np.percentile(vals, [33.3, 66.7]))

    c_range, c_rate, c_hnr, c_cent, c_loud = (cuts(k) for k in (
        "PitchRangeSemitones", "SpeechRateSylPerSec", "HNRdB", "SpectralCentroidHz", "LoudnessRangeDb"))
    for a in acoustics:
        a["TonalityLabel"] = label(a["PitchRangeSemitones"] or float("nan"), c_range, ("monotone", "moderate melody", "very melodic"))
        a["PacingLabel"] = label(a["SpeechRateSylPerSec"], c_rate, ("slow", "moderate", "rushed"))
        a["BreathinessLabel"] = label(a["HNRdB"], c_hnr, ("breathy/rough", "moderate", "clear/pure"))
        a["ResonanceLabel"] = label(a["SpectralCentroidHz"], c_cent, ("dark/warm", "neutral", "bright/thin"))
        a["DynamicsLabel"] = label(a["LoudnessRangeDb"], c_loud, ("even volume", "some contrast", "strong volume swings"))
        a["PauseLabel"] = ("no internal pauses" if a["PauseCount"] == 0 else
                           "one long pause" if a["PauseCount"] == 1 and a["LongestPauseSec"] >= 0.5 else
                           "phrased with pauses" if a["PauseCount"] <= 3 else "choppy, many pauses")

    write_csv(DATA / "acoustics.csv", acoustics)
    write_csv(DATA / "generations.csv", generations)
    print(f"analyzed {len(acoustics)} clips")


if __name__ == "__main__":
    main()
