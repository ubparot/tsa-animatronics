"""Word-choice and phrasing arm: the show's language model writing Pinocchio's line.

The exact prompt the show sends (pipeline.build_ollama_request) is reused, and
only the sampling options change: temperature, top_p, top_k, and the seed.

    python script_variants.py   -> data/script_variants.csv
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software_pipeline"))
from pipeline import build_ollama_request  # noqa: E402

from design import DATA, write_csv  # noqa: E402

MODEL = "pinocchio-fast"
QUESTIONS = [
    ("Q1", "What did you have for breakfast today?", "LIE"),
    ("Q2", "Did you build this whole workshop by yourself?", "CONFESSION"),
]
BASE = {"temperature": 0.5, "top_p": 0.9, "top_k": 40, "seed": 7}  # show temperature, Ollama's top_p/top_k
SWEEP = (
    [("baseline", "show defaults", {})]
    + [("temperature", f"T={t}", {"temperature": t}) for t in (0.0, 0.25, 0.8, 1.1, 1.5, 2.0)]
    + [("top_p", f"top_p={p}", {"top_p": p}) for p in (0.3, 0.6, 0.95, 1.0)]
    + [("top_k", f"top_k={k}", {"top_k": k}) for k in (1, 5, 100, 1000)]
    + [("seed only", f"seed={s}", {"seed": s}) for s in (101, 202, 303, 404, 505)]
)


def words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def ask(payload: dict) -> tuple[str, bool]:
    request = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        content = json.loads(response.read())["message"]["content"]
    try:
        return str(json.loads(content).get("spoken_text", "")).strip(), True
    except (json.JSONDecodeError, AttributeError):
        return content.strip()[:400], False


def main() -> None:
    rows = []
    for qid, question, tag in QUESTIONS:
        baseline_words: set[str] = set()
        for variable, level, change in SWEEP:
            opts = {**BASE, **change}
            _tag, _msg, payload = build_ollama_request(question, MODEL, tag_override=tag)
            payload["options"].update(opts)
            payload["keep_alive"] = "5m"
            text, valid = ask(payload)
            w = words(text)
            if variable == "baseline":
                baseline_words = set(w)
            overlap = len(set(w) & baseline_words) / max(1, len(set(w) | baseline_words))
            sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
            rows.append(dict(
                VariantID=f"V{len(rows) + 1:02d}", QuestionID=qid, VisitorQuestion=question, ShowOutcome=tag,
                VariableTested=variable, LevelLabel=level, Temperature=opts["temperature"], TopP=opts["top_p"],
                TopK=opts["top_k"], Seed=opts["seed"], GeneratedLine=text, ValidJSON=valid,
                WordCount=len(w), DistinctWordRatio=round(len(set(w)) / max(1, len(w)), 2),
                OverlapWithBaseline=round(overlap, 2), SentenceCount=len(sentences),
                Exclamations=text.count("!"), Questions=text.count("?"), Commas=text.count(","),
                OpeningWords=" ".join(text.split()[:3]),
            ))
            print(rows[-1]["VariantID"], level, "|", text, flush=True)
    write_csv(DATA / "script_variants.csv", rows)


if __name__ == "__main__":
    main()
