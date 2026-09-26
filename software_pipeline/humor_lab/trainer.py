"""Train a small, local Pinocchio humor preference model from Likert ratings.

This is intentionally a reranker, not a language-model fine-tune. With dozens of
human ratings it can learn which joke devices, deliveries, topics, and textual
traits this production prefers. It writes an interpretable JSON artifact that a
candidate generator can use later without adding a runtime dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
LINES_PATH = ROOT / "lines.json"
DATA_ROOT = Path(os.getenv("PINOCCHIO_HUMOR_DATA", ROOT / "data"))
RATINGS_PATH = DATA_ROOT / "ratings.jsonl"
MODEL_PATH = DATA_ROOT / "humor_model.json"
PROMPT_PATH = DATA_ROOT / "prompt_preferences.txt"
MINIMUM_RATINGS = 12
RIDGE_STRENGTH = 3.0


def load_experiment() -> dict[str, Any]:
    payload = json.loads(LINES_PATH.read_text(encoding="utf-8"))
    lines = payload.get("lines", [])
    ids = [line.get("id") for line in lines]
    if not lines or len(ids) != len(set(ids)):
        raise ValueError("Humor lines must have unique IDs.")
    return payload


def load_ratings(path: Path = RATINGS_PATH) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def latest_ratings(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep edits, but make each rater/line pair one training example."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("rater_id", "")), str(record.get("line_id", "")))
        if key[0] and key[1]:
            latest[key] = record
    return list(latest.values())


def _base_features(line: dict[str, Any]) -> dict[str, float]:
    text = str(line["text"])
    lowered = text.lower()
    words = [word.strip(".,!?;:'\"") for word in text.split()]
    return {
        "bias": 1.0,
        f"device:{line['device']}": 1.0,
        f"delivery:{line['delivery']}": 1.0,
        f"topic:{line['topic']}": 1.0,
        "text:words": min(len(words), 35) / 20.0,
        "text:sentences": min(text.count(".") + text.count("!") + text.count("?"), 4) / 2.0,
        "text:question": float("?" in text),
        "text:exclamation": float("!" in text),
        "text:first_person": min(sum(word.lower() in {"i", "i'm", "i've", "my", "me"} for word in words), 5) / 3.0,
        "text:contrast_turn": float(any(token in lowered for token in (" but ", " unfortunately", " actually", " except ", " only "))),
        "text:character_callback": float(any(token in lowered for token in ("nose", "wood", "pine", "geppetto", "cricket", "puppet", "strings"))),
    }


def _feature_names(lines: list[dict[str, Any]], ratings: list[dict[str, Any]]) -> list[str]:
    by_id = {line["id"]: line for line in lines}
    counts: Counter[str] = Counter()
    for rating in ratings:
        line = by_id.get(rating["line_id"])
        if line:
            counts.update(_base_features(line))
    fixed = {name for name in counts if name == "bias" or name.startswith("text:")}
    repeated = {name for name, count in counts.items() if count >= 2}
    return ["bias"] + sorted((fixed | repeated) - {"bias"})


def _vector(line: dict[str, Any], names: list[str]) -> list[float]:
    features = _base_features(line)
    return [features.get(name, 0.0) for name in names]


def _solve(matrix: list[list[float]], values: list[float]) -> list[float]:
    """Solve a dense linear system with partial-pivot Gaussian elimination."""
    size = len(values)
    augmented = [row[:] + [values[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-10:
            augmented[pivot][column] = 1e-10
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor:
                augmented[row] = [
                    current - factor * reference
                    for current, reference in zip(augmented[row], augmented[column])
                ]
    return [augmented[index][-1] for index in range(size)]


def _fit(x_rows: list[list[float]], targets: list[float], ridge: float = RIDGE_STRENGTH) -> list[float]:
    width = len(x_rows[0])
    matrix = [[0.0] * width for _ in range(width)]
    values = [0.0] * width
    for row, target in zip(x_rows, targets):
        for left in range(width):
            values[left] += row[left] * target
            for right in range(width):
                matrix[left][right] += row[left] * row[right]
    for index in range(1, width):  # Do not shrink the intercept.
        matrix[index][index] += ridge
    matrix[0][0] += 1e-8
    return _solve(matrix, values)


def _predict(row: list[float], coefficients: list[float]) -> float:
    return max(1.0, min(7.0, sum(value * weight for value, weight in zip(row, coefficients))))


def _cross_validation(
    examples: list[tuple[str, list[float], float]],
    folds: int = 5,
) -> dict[str, float] | None:
    if len(examples) < 20:
        return None
    errors: list[float] = []
    baseline_errors: list[float] = []
    for fold in range(folds):
        train = [item for item in examples if int(hashlib.sha256(item[0].encode()).hexdigest(), 16) % folds != fold]
        test = [item for item in examples if int(hashlib.sha256(item[0].encode()).hexdigest(), 16) % folds == fold]
        if not train or not test:
            continue
        coefficients = _fit([item[1] for item in train], [item[2] for item in train])
        baseline = statistics.mean(item[2] for item in train)
        errors.extend(abs(_predict(row, coefficients) - target) for _, row, target in test)
        baseline_errors.extend(abs(baseline - target) for _, _, target in test)
    if not errors:
        return None
    return {
        "mean_absolute_error": round(statistics.mean(errors), 3),
        "baseline_mean_absolute_error": round(statistics.mean(baseline_errors), 3),
    }


def _group_insights(lines_by_id: dict[str, dict[str, Any]], ratings: list[dict[str, Any]], global_mean: float) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    prior_weight = 4.0
    for field in ("device", "delivery", "topic"):
        groups: defaultdict[str, list[float]] = defaultdict(list)
        for rating in ratings:
            line = lines_by_id.get(rating["line_id"])
            if line:
                groups[str(line[field])].append(float(rating["rating"]))
        entries = []
        for name, values in groups.items():
            raw_mean = statistics.mean(values)
            shrunk = (sum(values) + prior_weight * global_mean) / (len(values) + prior_weight)
            entries.append({
                "name": name,
                "count": len(values),
                "mean": round(raw_mean, 3),
                "preference_score": round(shrunk, 3),
            })
        output[field] = sorted(entries, key=lambda item: (-item["preference_score"], -item["count"], item["name"]))
    return output


def train_model(
    ratings_path: Path = RATINGS_PATH,
    model_path: Path = MODEL_PATH,
    prompt_path: Path = PROMPT_PATH,
) -> dict[str, Any]:
    experiment = load_experiment()
    lines = experiment["lines"]
    lines_by_id = {line["id"]: line for line in lines}
    ratings = [
        rating for rating in latest_ratings(load_ratings(ratings_path))
        if rating.get("line_id") in lines_by_id and isinstance(rating.get("rating"), int) and 1 <= rating["rating"] <= 7
    ]
    if len(ratings) < MINIMUM_RATINGS:
        raise ValueError(f"Rate at least {MINIMUM_RATINGS} lines before training; currently {len(ratings)}.")

    names = _feature_names(lines, ratings)
    examples = [
        (
            f"{rating['rater_id']}:{rating['line_id']}",
            _vector(lines_by_id[rating["line_id"]], names),
            float(rating["rating"]),
        )
        for rating in ratings
    ]
    coefficients = _fit([item[1] for item in examples], [item[2] for item in examples])
    global_mean = statistics.mean(item[2] for item in examples)
    predictions = {
        line["id"]: round(_predict(_vector(line, names), coefficients), 3)
        for line in lines
    }
    insights = _group_insights(lines_by_id, ratings, global_mean)
    rated_means: defaultdict[str, list[int]] = defaultdict(list)
    for rating in ratings:
        rated_means[rating["line_id"]].append(rating["rating"])
    ranked_rated = sorted(
        (
            {
                "id": line_id,
                "text": lines_by_id[line_id]["text"],
                "mean": round(statistics.mean(values), 3),
                "count": len(values),
            }
            for line_id, values in rated_means.items()
        ),
        key=lambda item: (-item["mean"], -item["count"], item["id"]),
    )
    model = {
        "format": "pinocchio_humor_reranker_v1",
        "trained_at": time.time(),
        "training_examples": len(ratings),
        "unique_raters": len({rating["rater_id"] for rating in ratings}),
        "global_mean": round(global_mean, 3),
        "ridge_strength": RIDGE_STRENGTH,
        "feature_names": names,
        "coefficients": [round(value, 8) for value in coefficients],
        "cross_validation": _cross_validation(examples),
        "insights": insights,
        "top_rated_lines": ranked_rated[:8],
        "lowest_rated_lines": list(reversed(ranked_rated[-8:])),
        "line_predictions": predictions,
        "warning": "Preference reranker for candidate selection; not a Chatterbox voice-model fine-tune.",
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    prompt_path.write_text(_prompt_preferences(model), encoding="utf-8")
    return model


def _prompt_preferences(model: dict[str, Any]) -> str:
    favorite_devices = [item["name"].replace("_", " ") for item in model["insights"]["device"][:3]]
    weak_devices = [item["name"].replace("_", " ") for item in model["insights"]["device"][-2:]]
    examples = "\n".join(f"- {item['text']}" for item in model["top_rated_lines"][:4])
    return (
        "PINOCCHIO HUMOR PREFERENCES\n"
        f"Favor these tested joke structures: {', '.join(favorite_devices)}.\n"
        f"Use these sparingly unless context demands them: {', '.join(weak_devices)}.\n"
        "Keep the visitor safe from ridicule; make Pinocchio's overconfidence the target.\n"
        "Use one clear setup and one concise turn. Do not copy examples verbatim.\n"
        "High-rated examples:\n"
        f"{examples}\n"
    )


def public_summary(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "training_examples": model["training_examples"],
        "unique_raters": model["unique_raters"],
        "global_mean": model["global_mean"],
        "cross_validation": model["cross_validation"],
        "favorite_devices": model["insights"]["device"][:4],
        "favorite_deliveries": model["insights"]["delivery"][:4],
        "top_rated_lines": model["top_rated_lines"][:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the local Pinocchio humor preference reranker.")
    parser.add_argument("--ratings", type=Path, default=RATINGS_PATH)
    parser.add_argument("--output", type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    try:
        model = train_model(args.ratings, args.output, args.output.with_name("prompt_preferences.txt"))
    except ValueError as exc:
        print(exc)
        return 2
    metrics = model.get("cross_validation") or {}
    print(f"Trained on {model['training_examples']} ratings from {model['unique_raters']} rater(s).")
    print(f"Mean rating: {model['global_mean']:.2f}/7")
    if metrics:
        print(f"Cross-validated MAE: {metrics['mean_absolute_error']:.2f}")
    print(f"Model: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
