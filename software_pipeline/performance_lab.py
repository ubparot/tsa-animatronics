"""Experiment design helpers for the local Chatterbox Performance Lab.

A round compares *configurations*, not individual clips. Each configuration is
rendered across several seeds and several show lines, because at these
temperatures the seed alone moves delivery about as much as a temperature step
does. Rating one clip per setting mostly measures which seed got lucky.

    configuration = reference recording + temperature + repetition penalty
    cell          = one configuration speaking one line (rated as a group)
    take          = one seed inside a cell

The rater scores a cell after hearing every take in it, so seed variance is
something they hear rather than something that silently picks the winner.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import soundfile as sf


SEEDS = (20260920, 271828, 314159, 161803, 424242, 8675309)
TEMPERATURES = (0.68, 0.80, 0.94)
# Turbo ignores exaggeration, CFG and min_p, and a top-k of 1000 almost never
# binds under top-p 0.95. Repetition penalty is the second live delivery knob,
# and it is the one that clips or rushes the end of a long line.
REPETITION_PENALTIES = (1.00, 1.20, 1.35)

# Baseline first, then one-factor-at-a-time neighbours, so a delivery round
# answers "which knob moved this?" instead of "which corner won?".
DELIVERY_OFFSETS = (
    (0.00, 0.00),
    (-0.12, 0.00),
    (0.14, 0.00),
    (0.00, 0.15),
    (0.00, -0.20),
    (-0.12, 0.15),
    (0.14, -0.20),
)

# Dramatic beats first: the confession and the lie carry the show, and the long
# lines are where repetition penalty shows itself.
BATTERY_CATEGORIES = (
    "confession",
    "lie",
    "long",
    "greeting",
    "excited",
    "question",
    "whisper",
    "answer",
)

MAX_CONFIGS = 4
MAX_LINES = 4
MAX_SEEDS = 4
# Twelve groups of three takes is already a ~36-clip listening session. Past
# that the rater fatigues and the scores stop meaning anything.
MAX_CELLS = 12
CELL_IDS = "ABCDEFGHIJKLMNOP"
SECONDS_PER_CLIP = 2.8

RATING_KEYS = ("similarity", "naturalness", "character", "funniness")
RATING_WEIGHTS = {
    "similarity": 0.30,
    "naturalness": 0.25,
    "character": 0.25,
    "funniness": 0.20,
}


def discover_references(voice_training: Path) -> list[dict[str, Any]]:
    """Return the strongest long-form reference clips in a corpus."""
    wav_root = (voice_training / "wavs").resolve()
    transcripts: dict[str, str] = {}
    metadata = voice_training / "metadata.csv"
    if metadata.is_file():
        with metadata.open("r", encoding="utf-8-sig", newline="") as source:
            for row in csv.reader(source, delimiter="|"):
                if len(row) >= 2:
                    transcripts[Path(row[0]).name] = row[1].strip()

    candidates: list[dict[str, Any]] = []
    for path in wav_root.glob("*.wav"):
        try:
            duration = float(sf.info(str(path)).duration)
        except (RuntimeError, OSError):
            continue
        transcript = transcripts.get(path.name, "")
        # Long, sentence-like clips are much better cloning references than
        # number lists and isolated phrases.
        if not 7.5 <= duration <= 16.0 or len(transcript.split()) < 12:
            continue
        candidates.append(
            {
                "id": path.name,
                "path": str(path.resolve()),
                "duration": round(duration, 2),
                "transcript": transcript,
            }
        )
    # Turbo reads at most 10 s into the decoder and the first 150 speech tokens
    # (6 s) into the text model, so past about 11 s there is nothing to gain.
    candidates.sort(key=lambda item: (-min(item["duration"], 11.0), item["id"]))
    return candidates


def choose_references(
    candidates: list[dict[str, Any]], current_reference: Path, limit: int = 8
) -> list[dict[str, Any]]:
    """Choose varied long references while always retaining the live default."""
    by_id = {item["id"]: item for item in candidates}
    current = by_id.get(current_reference.name)
    chosen: list[dict[str, Any]] = [current] if current else []
    # Spread choices through the ranked pool rather than taking adjacent lines.
    remaining = [item for item in candidates if item is not current]
    if remaining:
        positions = [0, len(remaining) // 4, len(remaining) // 2, 3 * len(remaining) // 4, len(remaining) - 1]
        for position in positions:
            item = remaining[position]
            if item not in chosen:
                chosen.append(item)
            if len(chosen) >= limit:
                break
    for item in remaining:
        if len(chosen) >= limit:
            break
        if item not in chosen:
            chosen.append(item)
    return chosen[:limit]


def load_battery(path: Path) -> list[dict[str, Any]]:
    """Read the fixed voice test script used for multi-line rounds."""
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    battery: list[dict[str, Any]] = []
    for line in data.get("lines", []):
        plain = str(line.get("text") or "").strip()
        tagged = str(line.get("tagged") or "").strip()
        text = tagged or plain
        if not text:
            continue
        battery.append(
            {
                "id": str(line.get("id", "")),
                "category": str(line.get("category", "")),
                "text": text,
                "tagged": bool(tagged and tagged != plain),
            }
        )
    return battery


def choose_lines(
    battery: list[dict[str, Any]], custom_text: str, count: int
) -> list[dict[str, Any]]:
    """Put the operator line first, then span distinct show categories.

    A configuration that wins on a greeting can still fall apart on the
    confession beat, so one line per round cannot choose a show voice.
    """
    count = max(1, min(int(count), MAX_LINES))
    custom = custom_text.strip()
    if not custom:
        raise ValueError("Enter a performance line for the round.")
    lines: list[dict[str, Any]] = [
        {"id": "custom", "label": "Your line", "category": "custom", "text": custom}
    ]

    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in battery:
        by_category.setdefault(item["category"], []).append(item)
    for category in BATTERY_CATEGORIES:
        if len(lines) >= count:
            break
        options = by_category.get(category)
        if not options:
            continue
        # Prefer a line carrying paralinguistic tags: the tags are a real
        # delivery lever and they belong in the comparison.
        pick = next((item for item in options if item["tagged"]), options[0])
        lines.append(
            {
                "id": pick["id"],
                "label": category.title(),
                "category": category,
                "text": pick["text"],
            }
        )
    return lines[:count]


def build_configs(
    mode: str,
    references: list[dict[str, Any]],
    current: dict[str, Any],
    count: int = 3,
) -> list[dict[str, Any]]:
    """Create the configurations a round compares, without touching the live voice."""
    if mode not in {"reference", "delivery", "mixed"}:
        raise ValueError("Choose reference, delivery, or mixed exploration.")
    count = max(2, min(int(count), MAX_CONFIGS))
    if not references:
        raise ValueError("No usable reference recordings were found.")

    temperature = float(current["temperature"])
    repetition_penalty = float(current["repetition_penalty"])
    base = {
        "top_p": float(current["top_p"]),
        # Held fixed, never swept: under top-p 0.95 a top-k of 1000 is inert,
        # so sweeping it would spend clips on a knob that changes nothing.
        "top_k": int(current["top_k"]),
    }
    configs: list[dict[str, Any]] = []

    if mode == "reference":
        for reference in references[:count]:
            configs.append(
                {
                    **base,
                    "reference_path": reference["path"],
                    "reference_id": reference["id"],
                    "temperature": temperature,
                    "repetition_penalty": repetition_penalty,
                }
            )
    elif mode == "delivery":
        reference = references[0]
        seen: set[tuple[float, float]] = set()
        for temperature_offset, penalty_offset in DELIVERY_OFFSETS:
            if len(configs) >= count:
                break
            candidate = (
                round(_clamp(temperature + temperature_offset, 0.05, 5.0), 2),
                round(_clamp(repetition_penalty + penalty_offset, 1.0, 2.0), 2),
            )
            if candidate in seen:
                continue
            seen.add(candidate)
            configs.append(
                {
                    **base,
                    "reference_path": reference["path"],
                    "reference_id": reference["id"],
                    "temperature": candidate[0],
                    "repetition_penalty": candidate[1],
                }
            )
    else:
        temperatures = (temperature, TEMPERATURES[0], TEMPERATURES[-1])
        penalties = (repetition_penalty, REPETITION_PENALTIES[-1])
        for index in range(count):
            reference = references[index % len(references)]
            configs.append(
                {
                    **base,
                    "reference_path": reference["path"],
                    "reference_id": reference["id"],
                    "temperature": temperatures[index % len(temperatures)],
                    "repetition_penalty": penalties[index % len(penalties)],
                }
            )

    for index, config in enumerate(configs, start=1):
        config["config_id"] = index
    return configs


def build_round(
    mode: str,
    references: list[dict[str, Any]],
    current: dict[str, Any],
    battery: list[dict[str, Any]],
    custom_text: str,
    config_count: int = 3,
    line_count: int = 3,
    seed_count: int = 3,
) -> dict[str, Any]:
    """Lay out every cell and take in one blind comparison round."""
    configs = build_configs(mode, references, current, config_count)
    lines = choose_lines(battery, custom_text, line_count)
    seed_count = max(2, min(int(seed_count), MAX_SEEDS))
    seeds = list(SEEDS[:seed_count])

    if len(configs) * len(lines) > MAX_CELLS:
        raise ValueError(
            f"That round needs {len(configs) * len(lines)} rated cells; keep it to {MAX_CELLS}."
        )

    cells: list[dict[str, Any]] = []
    for config in configs:
        for line in lines:
            cells.append(
                {
                    "id": CELL_IDS[len(cells)],
                    "config_id": config["config_id"],
                    "line_id": line["id"],
                    "text": line["text"],
                    "takes": [
                        {"seed": seed, "index": index}
                        for index, seed in enumerate(seeds, start=1)
                    ],
                    "ratings": None,
                }
            )
    return {"configs": configs, "lines": lines, "seeds": seeds, "cells": cells}


def settings_for(config: dict[str, Any], seed: int) -> dict[str, Any]:
    """Render settings for one take. The live defaults are never consulted."""
    return {
        "reference_path": config["reference_path"],
        "temperature": config["temperature"],
        "top_p": config["top_p"],
        "top_k": config["top_k"],
        "repetition_penalty": config["repetition_penalty"],
        "seed": seed,
    }


def total_clips(round_plan: dict[str, Any]) -> int:
    return sum(len(cell["takes"]) for cell in round_plan["cells"])


def estimate_seconds(clips: int) -> int:
    return int(round(clips * SECONDS_PER_CLIP))


def validate_ratings(ratings: Any) -> dict[str, int]:
    if not isinstance(ratings, dict):
        raise ValueError("Ratings are required.")
    clean: dict[str, int] = {}
    for key in RATING_KEYS:
        value = ratings.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise ValueError(f"{key.title()} must be a whole number from 1 to 7.")
        value = int(value)
        if not 1 <= value <= 7:
            raise ValueError(f"{key.title()} must be from 1 to 7.")
        clean[key] = value
    return clean


def weighted_score(ratings: dict[str, int]) -> float:
    return round(sum(ratings[key] * RATING_WEIGHTS[key] for key in RATING_KEYS), 3)


def summarize_round(
    configs: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    cells: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank configurations by their mean score across every line in the round."""
    labels = {line["id"]: line["label"] for line in lines}
    grouped: dict[int, list[dict[str, Any]]] = {config["config_id"]: [] for config in configs}
    for cell in cells:
        if cell["ratings"] is None:
            raise ValueError("Rate every clip before revealing the settings.")
        grouped[cell["config_id"]].append(cell)

    results: list[dict[str, Any]] = []
    for config in configs:
        rated = grouped[config["config_id"]]
        scores = [weighted_score(cell["ratings"]) for cell in rated]
        breakdown = [
            {
                "lineId": cell["line_id"],
                "label": labels.get(cell["line_id"], cell["line_id"]),
                "cellId": cell["id"],
                "score": weighted_score(cell["ratings"]),
                "ratings": cell["ratings"],
            }
            for cell in rated
        ]
        results.append(
            {
                "configId": config["config_id"],
                "score": round(mean(scores), 2),
                # A config that is wonderful on one beat and broken on another
                # is worse for a live show than a steady one with a lower peak.
                "spread": round(max(scores) - min(scores), 2),
                "worst": round(min(scores), 2),
                "lines": breakdown,
                "settings": {
                    "referenceId": config["reference_id"],
                    "temperature": config["temperature"],
                    "repetitionPenalty": config["repetition_penalty"],
                    "topP": config["top_p"],
                    "topK": config["top_k"],
                },
            }
        )
    results.sort(key=lambda item: (-item["score"], item["spread"], item["configId"]))
    return results


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(float(value), maximum))
