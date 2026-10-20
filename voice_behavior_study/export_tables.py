"""Shape the study data into the final database tables (one CSV per table).

    python export_tables.py   -> db_tables/*.csv  (then build_database.ps1 makes the .accdb)

Tables
  Prompts            what text the model was asked to say
  ParameterSettings  the knob values for each condition
  Generations        one row per audio clip (links a prompt to a setting) + words heard
  AcousticBehavior   delivery measurements and plain-language labels per clip
  ListenerRatings    blind human perception ratings (from the listening session)
  ScriptVariants     language-model word choice and phrasing under different sampling
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import sys

from design import DATA, STUDY, read_csv

sys.path.insert(0, str(STUDY / "listen"))
from server import listening_set  # noqa: E402

OUT = STUDY / "db_tables"
TONES = ["cheerful", "warm", "remorseful / sad", "nervous", "sarcastic / dry", "excited", "whispery",
         "flat / robotic", "strange / uncanny"]


def write(name: str, rows: list[dict]) -> None:
    OUT.mkdir(exist_ok=True)
    with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{name}: {len(rows)} records, {len(rows[0])} fields")


def main() -> None:
    prompts = read_csv(DATA / "prompts.csv")
    write("Prompts", [{k: p[k] for k in (
        "PromptID", "PromptText", "Arm", "Category", "BaseSentence", "ManipulationCode", "Manipulation",
        "ManipulationType", "IntendedEffect", "IntendedEmotion", "SentenceType", "WordCount", "HasTag",
        "PunctuationMarks")} for p in prompts])

    pitch = json.loads((DATA / "rvc_pitch.json").read_text())
    settings = read_csv(DATA / "settings.csv")
    for s in settings:
        s["PitchShiftSemitones"] = pitch["pitch_shift"] if s["Engine"] == "Kokoro + RVC" and s["ConversionStrength"] else (
            0 if s["Engine"] == "Kokoro + RVC" else "")
    write("ParameterSettings", settings)

    gens = read_csv(DATA / "generations.csv")
    acoustic = {a["ClipID"]: a for a in read_csv(DATA / "acoustics.csv")}
    for g in gens:
        g["Engine"] = next(s["Engine"] for s in settings if s["SettingID"] == g["SettingID"])
        g["InListeningSession"] = False
        g["AudioPath"] = f"Z:/PinocchioBehaviorStudy/clips/{g['FileName']}"
        g["EndingBehavior"] = acoustic[g["ClipID"]]["EndingBehavior"]
    ratings_path = DATA / "ratings.jsonl"
    ratings = [json.loads(l) for l in ratings_path.read_text(encoding="utf-8").splitlines()] if ratings_path.is_file() else []
    session = {c["clip"] for c in listening_set()}
    for g in gens:
        g["InListeningSession"] = g["ClipID"] in session
    write("Generations", [{k: g[k] for k in (
        "ClipID", "SettingID", "PromptID", "StudyBlock", "Engine", "Seed", "DurationSec", "IntendedWords",
        "HeardTranscript", "WordBehavior", "WordBehaviorNotes", "EndingBehavior", "InListeningSession",
        "AudioPath")} for g in gens])

    write("AcousticBehavior", [{k: a[k] for k in (
        "ClipID", "MeanPitchHz", "PitchRangeSemitones", "PitchVariabilitySemitones", "IntonationContour",
        "TonalityLabel", "PauseCount", "LongestPauseSec", "TotalPauseSec", "PauseLabel", "SpeechRateSylPerSec",
        "PacingLabel", "F1Hz", "F2Hz", "SpectralCentroidHz", "ResonanceLabel", "LoudnessDb", "LoudnessRangeDb",
        "DynamicsLabel", "HNRdB", "BreathinessLabel", "VoicedFraction", "TrailingSec", "EndingBehavior")}
        for a in acoustic.values()])

    if ratings:
        rows = []
        for i, r in enumerate(ratings, 1):
            rows.append(dict(
                RatingID=f"R{i:03d}", ClipID=r["clip"], Listener=r["listener"], RatedAt=r["time"],
                PerceivedTone=r["tone"], EmotionMatch=r["emotion_match"], Expressiveness=r["expressiveness"],
                Naturalness=r["naturalness"], Breathiness=r["breathiness"], Articulation=r["articulation"],
                CharacterFit=r["character_fit"], Pacing=r["pacing"], Oddities="; ".join(r.get("oddities", [])),
                Notes=r.get("note", ""),
            ))
        write("ListenerRatings", rows)
    else:
        print("ListenerRatings: no ratings yet (run the listening session)")

    coding = {c["VariantID"]: c for c in read_csv(DATA / "script_coding.csv")}
    variants = read_csv(DATA / "script_variants.csv")
    for v in variants:
        v["GeneratedLine"] = v["GeneratedLine"].replace("\ufffd", "").strip()
        v["EndsMidSentence"] = not v["GeneratedLine"].rstrip().endswith((".", "!", "?"))
        v.update({k: coding[v["VariantID"]][k] for k in ("ToneCode", "FitsOutcome", "PhrasingNote")})
    write("ScriptVariants", variants)


if __name__ == "__main__":
    main()
