"""Lip-sync and expression tracks for the 7-servo mouth (WORK_PRODUCT/18_Mouth_Revamp).

A spoken line becomes a timed viseme list (from the text, or from phoneme timings
when a TTS engine provides them). The visemes become pose weights over time, which
mouth_poses.blend() mixes in lip-node space. An optional expression (smile, frown,
surprise, ...) is layered on top. The node trajectory is smoothed and rate limited,
then mouth_poses.servo_angles() converts each frame into per-channel servo offsets
and range-checks it.

Offsets are degrees from each servo's neutral (JAW_OPEN_DEG is degrees of jaw
opening), computed from the PLACEHOLDER SG90 geometry in mouth_poses.py. Nothing
here is calibrated: the real controller still owns neutrals, directions and hard
limits. The model never commands these channels; the host derives them from the
line it is about to speak.

    python mouth_track.py "Hello there, friend!" --expression smile --out track.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

import numpy as np

ROOT = Path(__file__).resolve().parent
MOUTH_DIR_ENV = "PINOCCHIO_MOUTH_DIR"
# mouth_poses.py stays in the canonical work product; it is loaded from there, not copied.
MOUTH_DIR_CANDIDATES = (
    ROOT.parent / "WORK_PRODUCT" / "18_Mouth_Revamp",
    Path(
        r"Z:\Downloads\Codex_Work_Block_Instructions-20261012T225555Z-1-001"
        r"\Codex_Work_Block_Instructions\WORK_PRODUCT\18_Mouth_Revamp"
    ),
)

TRACK_FORMAT = "pinocchio_mouth_track/1"
MOUTH_CHANNELS = (
    "JAW_OPEN_DEG",
    "CORNER_L_A",
    "CORNER_L_B",
    "CORNER_R_A",
    "CORNER_R_B",
    "UPPER_LIP",
    "LOWER_LIP",
)
VISEMES = ("AI", "E", "O", "U", "MBP", "FV", "L", "WQ", "etc", "rest")
EXPRESSIONS = ("neutral", "smile", "big_smile", "frown", "sneer_left", "surprise")

# Node vector layout used for smoothing: jaw deg, left corner dx/dz, right corner dx/dz, upper/lower lip dz (mm).
JAW, CLX, CLZ, CRX, CRZ, UPPER, LOWER = range(7)

# How strongly a full-strength expression pulls each part of the speaking mouth toward its own pose.
# Speech keeps the jaw and most of the lips, so a smiling line is still readable.
EXPRESSION_GAIN = np.array([0.35, 0.85, 0.85, 0.85, 0.85, 0.5, 0.35])

# PLACEHOLDER motion limits (not measured). Smoothing time constants (s) per node component, and slew limits:
# jaw deg/s, corner node mm/s (vector speed), lip node mm/s. The five-bar and the short lip levers turn node
# speed into a lot of horn speed, so every mouth servo is also capped at SERVO_SLEW_DEG_S (SG90 is ~600 deg/s
# unloaded at 4.8 V; the TPU lips load it).
SMOOTH_TAU_S = np.array([0.025, 0.04, 0.04, 0.04, 0.04, 0.025, 0.025])
JAW_SLEW_DEG_S = 150.0
CORNER_SLEW_MM_S = 60.0
LIP_SLEW_MM_S = 50.0
SERVO_SLEW_DEG_S = 300.0

# Text timing: relative duration of each viseme, speaking rate, and pauses for punctuation.
VISEME_UNITS = {"AI": 1.0, "E": 0.9, "O": 1.0, "U": 0.9, "MBP": 0.8, "FV": 0.7, "L": 0.6, "WQ": 0.7, "etc": 0.55}
UNITS_PER_S = 9.0
MIN_VISEME_S = 0.05
PAUSE_S = {"...": 0.35, ".": 0.3, "!": 0.3, "?": 0.3, ",": 0.15, ";": 0.18, ":": 0.18, "-": 0.12}
# Lips are pressed for M/B/P and the lower lip is tucked for F/V: these win over neighbours and expressions.
VISEME_PRIORITY = {"MBP": 1.6, "FV": 1.2}
COARTICULATION_S = 0.07   # cosine ramp either side of each viseme
LEAD_S = 0.06             # mouth leads the audio slightly (servo lag + perception)
EXPRESSION_RAMP_S = 0.2

VOICE_TAG_EXPRESSIONS = {"laugh": ("big_smile", 0.8), "chuckle": ("smile", 0.7), "gasp": ("surprise", 0.7), "sigh": ("frown", 0.5)}
TAG_EXPRESSIONS = {"TRUTH": ("smile", 0.3), "LIE": ("sneer_left", 0.45), "CONFESSION": ("frown", 0.45)}


@dataclass(frozen=True)
class VisemeEvent:
    viseme: str
    start: float
    end: float


def _find_mouth_dir() -> Path:
    candidates = [Path(os.environ[MOUTH_DIR_ENV])] if os.environ.get(MOUTH_DIR_ENV) else []
    candidates += list(MOUTH_DIR_CANDIDATES)
    for folder in candidates:
        if (folder / "mouth_poses.py").is_file():
            return folder
    raise ImportError(
        f"mouth_poses.py not found; set {MOUTH_DIR_ENV} to the 18_Mouth_Revamp folder "
        f"(tried {', '.join(str(c) for c in candidates)})"
    )


@lru_cache(maxsize=1)
def mouth_poses() -> ModuleType:
    """Load the canonical mouth_poses.py (pure numpy) without adding its folder to sys.path."""
    path = _find_mouth_dir() / "mouth_poses.py"
    spec = importlib.util.spec_from_file_location("mouth_poses", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mouth_available() -> bool:
    try:
        mouth_poses()
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------- text -> visemes

# Spelling rules, longest first. Rough English letter-to-viseme groups, good enough for a puppet mouth.
_SPELLING = (
    ("tion", ("etc", "AI", "etc")), ("ough", ("O",)), ("eigh", ("E",)),
    ("igh", ("AI",)), ("tch", ("etc",)), ("dge", ("etc",)), ("sch", ("etc",)),
    ("th", ("L",)), ("sh", ("etc",)), ("ch", ("etc",)), ("ph", ("FV",)), ("wh", ("WQ",)),
    ("qu", ("etc", "WQ")), ("ck", ("etc",)), ("ng", ("etc",)), ("gh", ()), ("kn", ("etc",)), ("wr", ("etc",)),
    ("ee", ("E",)), ("ea", ("E",)), ("ie", ("E",)), ("ei", ("E",)), ("ey", ("E",)),
    ("oo", ("U",)), ("ew", ("U",)), ("ue", ("U",)), ("ui", ("U",)),
    ("ou", ("O",)), ("ow", ("O",)), ("oa", ("O",)), ("oe", ("O",)), ("oi", ("O", "E")), ("oy", ("O", "E")),
    ("ai", ("AI",)), ("ay", ("AI",)), ("au", ("O",)), ("aw", ("O",)),
    ("a", ("AI",)), ("i", ("AI",)), ("e", ("E",)), ("o", ("O",)), ("u", ("U",)),
    ("m", ("MBP",)), ("b", ("MBP",)), ("p", ("MBP",)), ("f", ("FV",)), ("v", ("FV",)),
    ("l", ("L",)), ("w", ("WQ",)), ("y", ("E",)),
)
_DIGITS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
# ARPAbet (CMU dict, stress digits stripped) to viseme, for engines that return phoneme timings.
ARPABET_VISEMES = {
    "AA": "AI", "AE": "AI", "AH": "AI", "AY": "AI", "EY": "E", "EH": "E", "IH": "E", "IY": "E", "ER": "etc",
    "AO": "O", "OW": "O", "OY": "O", "AW": "O", "UH": "U", "UW": "U",
    "M": "MBP", "B": "MBP", "P": "MBP", "F": "FV", "V": "FV", "L": "L", "TH": "L", "DH": "L",
    "W": "WQ", "Y": "E", "R": "etc", "HH": "etc", "SIL": "rest", "SP": "rest", "PAU": "rest",
}


def split_voice_tags(text: str) -> tuple[str, list[str]]:
    """Remove [chuckle]-style voice tags from a line; return the speakable text and the tag names."""
    tags = [tag.lower() for tag in re.findall(r"\[([a-zA-Z_]+)\]", text)]
    return re.sub(r"\[[a-zA-Z_]+\]", " ", text), tags


def word_visemes(word: str) -> list[str]:
    word = re.sub(r"[^a-z]", "", word.lower())
    # Silent final e ("make", "shine") when the word already has another vowel.
    if len(word) > 2 and word.endswith("e") and word[-2] not in "aeiouy" and re.search(r"[aeiouy]", word[:-2]):
        word = word[:-1]
    if word.endswith("mb") or (len(word) > 1 and word.endswith("h") and word[-2] in "aeiou"):
        word = word[:-1]   # "lamb", "oh", "ah"
    out: list[str] = []
    i = 0
    while i < len(word):
        if i and word[i] == word[i - 1] and word[i] not in "eo":
            i += 1   # doubled consonant/vowel letters are one sound ("ee"/"oo" are handled as digraphs)
            continue
        for spelling, visemes in _SPELLING:
            if word.startswith(spelling, i):
                if spelling == "y" and i == 0:
                    visemes = ("etc",)
                out.extend(visemes)
                i += len(spelling)
                break
        else:
            out.append("etc")
            i += 1
    merged: list[str] = []
    for v in out:
        if not merged or merged[-1] != v:
            merged.append(v)
    return merged


def text_to_visemes(text: str, duration_s: float | None = None, rate: float = UNITS_PER_S) -> list[VisemeEvent]:
    """Timed visemes for a line of dialogue (time 0 = start of audio).

    Without audio, timing comes from a nominal speaking rate. When the TTS audio length is
    known, pass duration_s and the speech is stretched to fill it.
    """
    text, _ = split_voice_tags(text)
    text = re.sub(r"\d", lambda m: f" {_DIGITS[int(m.group())]} ", text)
    tokens = re.findall(r"\.\.\.|[.!?,;:]|\s-\s|[A-Za-z']+", text)
    plan: list[tuple[str, float]] = []   # (viseme, units) or ("rest", seconds as negative units)
    for token in tokens:
        token = token.strip()
        if token in PAUSE_S:
            if plan and plan[-1][0] != "rest":
                plan.append(("rest", -PAUSE_S[token]))
            continue
        for v in word_visemes(token):
            plan.append((v, VISEME_UNITS[v]))
    while plan and plan[-1][0] == "rest":
        plan.pop()
    if not plan:
        return []
    speech_units = sum(u for _, u in plan if u > 0)
    pause_s = -sum(u for _, u in plan if u < 0)
    unit_s = 1.0 / rate
    pause_scale = 1.0
    if duration_s is not None and duration_s > 0:
        if pause_s > 0.3 * duration_s:
            pause_scale = 0.3 * duration_s / pause_s
        unit_s = max(duration_s - pause_s * pause_scale, 1e-3) / speech_units
    events: list[VisemeEvent] = []
    t = 0.0
    for viseme, units in plan:
        dur = -units * pause_scale if units < 0 else max(units * unit_s, MIN_VISEME_S)
        if events and events[-1].viseme == viseme:
            events[-1] = VisemeEvent(viseme, events[-1].start, t + dur)
        else:
            events.append(VisemeEvent(viseme, t, t + dur))
        t += dur
    return events


def phonemes_to_visemes(phonemes: Iterable[tuple[str, float, float]]) -> list[VisemeEvent]:
    """Timed visemes from (ARPAbet phoneme, start s, end s) triples, e.g. from a forced aligner."""
    events: list[VisemeEvent] = []
    for phone, start, end in phonemes:
        viseme = ARPABET_VISEMES.get(re.sub(r"\d", "", phone.upper()), "etc")
        if events and events[-1].viseme == viseme and abs(events[-1].end - start) < 1e-6:
            events[-1] = VisemeEvent(viseme, events[-1].start, float(end))
        else:
            events.append(VisemeEvent(viseme, float(start), float(end)))
    return events


# ---------------------------------------------------------------- visemes -> weights -> nodes

def viseme_weights(events: list[VisemeEvent], times: np.ndarray) -> dict[str, np.ndarray]:
    """Normalised pose weights per frame: a plateau over each viseme with cosine coarticulation ramps."""
    raw = {"rest": np.full(times.shape, 1e-3)}   # always some rest, so silence and the track ends are at rest
    for event in events:
        before = np.clip((event.start - times) / COARTICULATION_S, 0.0, 1.0)
        after = np.clip((times - event.end) / COARTICULATION_S, 0.0, 1.0)
        window = 0.5 * (1.0 + np.cos(np.pi * np.maximum(before, after)))
        raw[event.viseme] = raw.get(event.viseme, 0.0) + window * VISEME_PRIORITY.get(event.viseme, 1.0)
    total = sum(raw.values())
    return {name: w / total for name, w in raw.items()}


def _pose_vector(pose: dict[str, Any]) -> np.ndarray:
    return np.array([pose["jaw"], *pose["CL"], *pose["CR"], pose["U"], pose["L"]], float)


def _vector_pose(v: np.ndarray) -> dict[str, Any]:
    return dict(jaw=float(v[JAW]), CL=(float(v[CLX]), float(v[CLZ])), CR=(float(v[CRX]), float(v[CRZ])),
                U=float(v[UPPER]), L=float(v[LOWER]))


def parse_expression(value: str | None, default_strength: float = 0.8) -> tuple[str, float] | None:
    """'smile' or 'smile:0.6' -> ('smile', 0.6). None or '' -> None."""
    if not value:
        return None
    name, _, strength = value.partition(":")
    name = name.strip()
    if name not in EXPRESSIONS:
        raise ValueError(f"unknown expression {name!r}; choose from {', '.join(EXPRESSIONS)}")
    s = float(strength) if strength else default_strength
    return name, max(0.0, min(1.0, s))


def expression_envelope(times: np.ndarray, start: float, end: float, release: bool) -> np.ndarray:
    rise = np.clip((times - start) / EXPRESSION_RAMP_S, 0.0, 1.0)
    if not release:
        return 0.5 - 0.5 * np.cos(np.pi * rise)
    fall = np.clip((end - times) / EXPRESSION_RAMP_S, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * np.minimum(rise, fall))


def smooth_and_limit(nodes: np.ndarray, dt: float, to_servo=None) -> np.ndarray:
    """One-pole smoothing then slew limiting, in node space. Each step only shortens the move toward the
    target, so every frame stays inside the convex travel boxes that blend() respects. With to_servo
    (node vector -> {channel: deg}), a step is also shortened until no mouth servo exceeds SERVO_SLEW_DEG_S."""
    alpha = 1.0 - np.exp(-dt / SMOOTH_TAU_S)
    out = np.empty_like(nodes)
    cur = nodes[0].copy()
    prev_servo = to_servo(cur) if to_servo else None
    groups = ((slice(JAW, JAW + 1), JAW_SLEW_DEG_S), (slice(CLX, CLZ + 1), CORNER_SLEW_MM_S),
              (slice(CRX, CRZ + 1), CORNER_SLEW_MM_S), (slice(UPPER, UPPER + 1), LIP_SLEW_MM_S),
              (slice(LOWER, LOWER + 1), LIP_SLEW_MM_S))
    for i, target in enumerate(nodes):
        want = cur + alpha * (target - cur)
        for part, slew in groups:
            step = want[part] - cur[part]
            norm = float(np.linalg.norm(step))
            limit = slew * dt
            want[part] = cur[part] + (step if norm <= limit else step * (limit / norm))
        if to_servo:
            move = want - cur
            for _ in range(8):
                servo = to_servo(cur + move)
                rate = max(abs(servo[ch] - prev_servo[ch]) for ch in servo if ch != "JAW_OPEN_DEG") / dt
                if rate <= SERVO_SLEW_DEG_S * (1 + 1e-6):
                    break
                move *= 0.98 * SERVO_SLEW_DEG_S / rate
            else:
                move[:] = 0.0
                servo = prev_servo
            want = cur + move
            prev_servo = servo
        cur = want
        out[i] = cur
    return out


# ---------------------------------------------------------------- track

def build_mouth_track(
    events: list[VisemeEvent],
    expression: tuple[str, float] | None = None,
    rate_hz: float = 50.0,
    lead_s: float = LEAD_S,
    hold_expression: bool = False,
    min_duration_s: float = 0.0,
) -> dict[str, Any]:
    """Per-channel servo offset track (deg from neutral) for timed visemes plus an optional expression."""
    mp = mouth_poses()
    dt = 1.0 / rate_hz
    shifted = [VisemeEvent(e.viseme, e.start - lead_s, e.end - lead_s) for e in events if e.end > e.start]
    speech_end = max([e.end for e in shifted] + [min_duration_s])
    t0 = min([e.start for e in shifted] + [0.0]) - COARTICULATION_S
    t1 = speech_end + COARTICULATION_S + 0.25    # settle back to rest (or into the held expression)
    times = t0 + dt * np.arange(int(math.ceil((t1 - t0) / dt)) + 1)

    weights = viseme_weights(shifted, times)
    names = list(weights)
    nodes = np.array([
        _pose_vector(mp.blend({n: float(weights[n][i]) for n in names if weights[n][i] > 1e-6}))
        for i in range(len(times))
    ])

    if expression is not None:
        name, strength = expression
        target = _pose_vector(mp.POSES[name])
        envelope = strength * expression_envelope(times, t0, t1 - 0.1, release=not hold_expression)
        gain = np.tile(EXPRESSION_GAIN, (len(times), 1))
        closure = weights.get("MBP", 0.0) + weights.get("FV", 0.0)
        gain[:, UPPER] *= 1.0 - closure
        gain[:, LOWER] *= 1.0 - closure
        nodes = nodes + gain * envelope[:, None] * (target - nodes)

    nodes = smooth_and_limit(nodes, dt, lambda v: mp.servo_angles(_vector_pose(v)))
    frames = [mp.servo_angles(_vector_pose(v)) for v in nodes]   # raises if any frame leaves the safe range
    tracks = {ch: [round(float(f[ch]), 3) + 0.0 for f in frames] for ch in MOUTH_CHANNELS}
    peak_rate = {
        ch: round(float(np.max(np.abs(np.diff(tracks[ch])))) / dt, 1) if len(times) > 1 else 0.0
        for ch in MOUTH_CHANNELS
    }
    return {
        "format": TRACK_FORMAT,
        "units": "deg offset from each servo's neutral; JAW_OPEN_DEG is deg of jaw opening",
        "calibration": "placeholder SG90 geometry from mouth_poses.py, not measured",
        "rate_hz": rate_hz,
        "start_s": round(float(times[0]), 4),
        "duration_s": round(float(times[-1] - times[0]), 4),
        "channels": list(MOUTH_CHANNELS),
        "tracks": tracks,
        "visemes": [{"viseme": e.viseme, "start": round(e.start, 3), "end": round(e.end, 3)} for e in events],
        "expression": {"name": expression[0], "strength": expression[1], "hold": hold_expression} if expression else None,
        "peak_rate_deg_s": peak_rate,
    }


def mouth_track_from_text(
    text: str,
    expression: str | tuple[str, float] | None = None,
    duration_s: float | None = None,
    rate_hz: float = 50.0,
    hold_expression: bool = False,
) -> dict[str, Any]:
    """Lip-sync track for one line. expression: 'smile', 'smile:0.6', ('smile', 0.6) or None (use voice tags)."""
    if isinstance(expression, str):
        expression = parse_expression(expression)
    if expression is None:
        expression = expression_for_line(text)
    events = text_to_visemes(text, duration_s)
    return build_mouth_track(events, expression, rate_hz, hold_expression=hold_expression,
                             min_duration_s=duration_s or 0.0)


def expression_for_line(text: str, truth_tag: str | None = None, intensity: float = 0.5) -> tuple[str, float] | None:
    """A voice tag in the line ([laugh], [gasp], ...) picks the expression; otherwise the truth tag, if given."""
    _, tags = split_voice_tags(text)
    for tag in tags:
        if tag in VOICE_TAG_EXPRESSIONS:
            return VOICE_TAG_EXPRESSIONS[tag]
    if truth_tag in TAG_EXPRESSIONS:
        name, base = TAG_EXPRESSIONS[truth_tag]
        return name, round(base * (0.5 + intensity), 3)
    return None


def mouth_track_for_packet(
    packet: dict[str, Any],
    expression: str | tuple[str, float] | None = None,
    duration_s: float | None = None,
    rate_hz: float = 50.0,
) -> dict[str, Any]:
    """Track for a validated show packet. An explicit expression overrides the one derived from the packet."""
    if isinstance(expression, str):
        expression = parse_expression(expression)
    if expression is None:
        expression = expression_for_line(
            packet["spoken_text"], packet.get("truth_tag"), float(packet.get("emotion_intensity", 0.5))
        )
    return mouth_track_from_text(packet["spoken_text"], expression, duration_s, rate_hz)


def legacy_jaw_positions(track: dict[str, Any]) -> list[float]:
    """JAW_OPEN_DEG as 0..1 positions for controllers that still only know the old `jaw` axis."""
    jaw_max = mouth_poses().JAW_MAX_DEG
    return [round(max(0.0, min(1.0, v / jaw_max)), 3) for v in track["tracks"]["JAW_OPEN_DEG"]]


def validate_mouth_track(track: Any) -> tuple[bool, str]:
    if not isinstance(track, dict) or track.get("format") != TRACK_FORMAT:
        return False, "mouth_track has an unknown format"
    tracks = track.get("tracks")
    if not isinstance(tracks, dict) or tuple(track.get("channels", ())) != MOUTH_CHANNELS or set(tracks) != set(MOUTH_CHANNELS):
        return False, "mouth_track must have exactly the 7 mouth channels"
    lengths = {len(v) for v in tracks.values()}
    if len(lengths) != 1 or not lengths.pop():
        return False, "mouth_track channels must be non-empty and the same length"
    mp = mouth_poses()
    for ch, values in tracks.items():
        lo, hi = (0.0, mp.JAW_MAX_DEG) if ch == "JAW_OPEN_DEG" else (-mp.SERVO_LIMIT_DEG, mp.SERVO_LIMIT_DEG)
        if not all(isinstance(v, (int, float)) and lo - 1e-6 <= v <= hi + 1e-6 for v in values):
            return False, f"mouth_track {ch} outside {lo}..{hi} deg"
    return True, "ok"


def track_summary(track: dict[str, Any]) -> dict[str, Any]:
    """Small per-line record for logs: no per-frame data."""
    return {
        "format": track["format"],
        "frames": len(track["tracks"]["JAW_OPEN_DEG"]),
        "rate_hz": track["rate_hz"],
        "duration_s": track["duration_s"],
        "expression": track["expression"],
        "visemes": "".join(f"{v['viseme']} " for v in track["visemes"]).strip(),
        "range_deg": {ch: [min(v), max(v)] for ch, v in track["tracks"].items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a 7-channel mouth servo track for one line of dialogue.")
    parser.add_argument("text")
    parser.add_argument("--expression", help=f"one of {', '.join(EXPRESSIONS)}, optionally name:strength")
    parser.add_argument("--duration", type=float, help="audio length in seconds, if known")
    parser.add_argument("--rate", type=float, default=50.0, help="frames per second")
    parser.add_argument("--hold", action="store_true", help="hold the expression at the end instead of releasing it")
    parser.add_argument("--out", type=Path, help="write the full track JSON here (default: print a summary)")
    args = parser.parse_args(argv)
    track = mouth_track_from_text(args.text, args.expression, args.duration, args.rate, args.hold)
    if args.out:
        args.out.write_text(json.dumps(track, indent=1), encoding="utf-8")
        print(f"wrote {args.out}")
    print(json.dumps(track_summary(track), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
