"""Experimental design for the voice-generation behavioral study.

Everything the study varies is declared here as data, so the generator, the
analysis, the listening page and the Access database all read the same plan.

Design: one-factor-at-a-time sweeps around a baseline, with common random
numbers (every setting uses the same seed), plus a seed-only block that shows
how much delivery changes when *nothing* but the seed changes. A parameter
effect is only interpreted when it is larger than that seed-only spread.

Run:  python design.py      -> writes data/prompts.csv, data/settings.csv, data/plan.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

STUDY = Path(__file__).resolve().parent
DATA = STUDY / "data"
AUDIO_ROOT = Path("Z:/PinocchioBehaviorStudy")
CLIPS = AUDIO_ROOT / "clips"
VOICE_TRAINING = Path("E:/PinocchioVoiceTraining")

COMMON_SEED = 20261008
SEED_BLOCK = [11, 222, 3333, 44444, 555555, 6666666]

# ---------------------------------------------------------------- prompts --

# Three fixed show lines carry every parameter sweep.
SWEEP_LINES = [
    ("P01", "greeting", "Oh, a visitor! Come closer, I don't bite. I'm made of wood.", "cheerful welcome"),
    ("P02", "lie", "I am, of course, the king of a tiny kingdom hidden inside a clock.", "boastful lie"),
    ("P03", "confession", "I'm sorry. I wanted you to think I was braver than I am.", "remorseful confession"),
]

# Prompt arm: the same base sentence rewritten 14 ways. Only the text changes;
# the voice settings stay at the Turbo baseline.
PROMPT_BASES = {
    "A": ("lie", "boastful lie"),
    "B": ("confession", "remorseful confession"),
    "C": ("excited", "delighted surprise"),
}
# (code, manipulation, type, intended effect, {base: text})
MANIPULATIONS = [
    ("M00", "plain statement", "control", "neutral reference reading", {
        "A": "I never ate the cookies Geppetto left on the windowsill.",
        "B": "I broke the clock and hid the pieces under my bed.",
        "C": "You came all the way here just to see me.",
    }),
    ("M01", "exclamation mark", "punctuation", "raise energy and pitch", {
        "A": "I never ate the cookies Geppetto left on the windowsill!",
        "B": "I broke the clock and hid the pieces under my bed!",
        "C": "You came all the way here just to see me!",
    }),
    ("M02", "question mark", "punctuation", "rising final intonation", {
        "A": "I never ate the cookies Geppetto left on the windowsill?",
        "B": "I broke the clock and hid the pieces under my bed?",
        "C": "You came all the way here just to see me?",
    }),
    ("M03", "ellipsis pause", "punctuation", "insert a hesitant pause", {
        "A": "I never... ate the cookies Geppetto left on the windowsill.",
        "B": "I broke the clock... and hid the pieces under my bed.",
        "C": "You came all the way here... just to see me.",
    }),
    ("M04", "extra commas", "punctuation", "break the line into short phrases", {
        "A": "I, never, ate the cookies, Geppetto left, on the windowsill.",
        "B": "I, broke the clock, and hid, the pieces, under my bed.",
        "C": "You, came all the way here, just, to see me.",
    }),
    ("M05", "capitalised emphasis", "typography", "stress one word", {
        "A": "I NEVER ate the cookies Geppetto left on the windowsill.",
        "B": "I broke the clock and hid the pieces under my BED.",
        "C": "You came all the way here just to see ME.",
    }),
    ("M06", "[sigh] tag", "paralinguistic tag", "audible sigh, tired tone", {
        "A": "[sigh] I never ate the cookies Geppetto left on the windowsill.",
        "B": "[sigh] I broke the clock and hid the pieces under my bed.",
        "C": "[sigh] You came all the way here just to see me.",
    }),
    ("M07", "[chuckle] tag", "paralinguistic tag", "audible laugh, playful tone", {
        "A": "I never ate the cookies [chuckle] Geppetto left on the windowsill.",
        "B": "I broke the clock [chuckle] and hid the pieces under my bed.",
        "C": "You came all the way here [chuckle] just to see me.",
    }),
    ("M08", "[whispering] tag", "emotion tag", "quiet, breathy delivery", {
        "A": "[whispering] I never ate the cookies Geppetto left on the windowsill.",
        "B": "[whispering] I broke the clock and hid the pieces under my bed.",
        "C": "[whispering] You came all the way here just to see me.",
    }),
    ("M09", "[sarcastic] tag", "emotion tag", "dry, ironic tone", {
        "A": "[sarcastic] I never ate the cookies Geppetto left on the windowsill.",
        "B": "[sarcastic] I broke the clock and hid the pieces under my bed.",
        "C": "[sarcastic] You came all the way here just to see me.",
    }),
    ("M10", "[fear] tag", "emotion tag", "nervous, shaky tone", {
        "A": "[fear] I never ate the cookies Geppetto left on the windowsill.",
        "B": "[fear] I broke the clock and hid the pieces under my bed.",
        "C": "[fear] You came all the way here just to see me.",
    }),
    ("M11", "written hesitation", "lexical", "stammer and filler word", {
        "A": "I-I never, um, ate the cookies Geppetto left on the windowsill.",
        "B": "I-I broke the clock and, um, hid the pieces under my bed.",
        "C": "You-you came all the way here, um, just to see me.",
    }),
    ("M12", "stretched spelling", "lexical", "drawn-out vowel", {
        "A": "I neeever ate the cookies Geppetto left on the windowsill.",
        "B": "I broke the clock and hid the pieces under my beeed.",
        "C": "You came aaall the way here just to see me.",
    }),
    ("M13", "written stage direction", "lexical", "test whether the cue is acted or read aloud", {
        "A": "(whispering) I never ate the cookies Geppetto left on the windowsill.",
        "B": "(whispering) I broke the clock and hid the pieces under my bed.",
        "C": "(whispering) You came all the way here just to see me.",
    }),
]

TAGS = ("[sigh]", "[chuckle]", "[whispering]", "[sarcastic]", "[fear]")


def spoken_words(text: str) -> list[str]:
    """Words a listener should hear: tags and stage directions removed."""
    clean = text
    for tag in TAGS:
        clean = clean.replace(tag, " ")
    clean = clean.replace("(whispering)", " ")
    return [w for w in clean.replace("...", " ").split() if any(c.isalpha() for c in w)]


def sentence_type(text: str) -> str:
    stripped = text.rstrip()
    if stripped.endswith("?"):
        return "question"
    if stripped.endswith("!"):
        return "exclamation"
    return "statement"


def build_prompts() -> list[dict]:
    rows = []
    for pid, category, text, emotion in SWEEP_LINES:
        rows.append(dict(
            PromptID=pid, PromptText=text, Arm="parameter sweep line", Category=category,
            BaseSentence="", ManipulationCode="", Manipulation="none (fixed sweep line)",
            ManipulationType="none", IntendedEffect=emotion, IntendedEmotion=emotion,
            SentenceType=sentence_type(text), WordCount=len(spoken_words(text)),
            HasTag=any(t in text for t in TAGS), PunctuationMarks=sum(text.count(c) for c in ",.!?;"),
        ))
    n = len(rows)
    for base, (category, emotion) in PROMPT_BASES.items():
        for code, name, kind, effect, texts in MANIPULATIONS:
            n += 1
            text = texts[base]
            rows.append(dict(
                PromptID=f"P{n:02d}", PromptText=text, Arm="prompt manipulation", Category=category,
                BaseSentence=base, ManipulationCode=code, Manipulation=name, ManipulationType=kind,
                IntendedEffect=effect, IntendedEmotion=emotion, SentenceType=sentence_type(text),
                WordCount=len(spoken_words(text)), HasTag=any(t in text for t in TAGS),
                PunctuationMarks=sum(text.count(c) for c in ",.!?;"),
            ))
    return rows


# --------------------------------------------------------------- settings --

TURBO_BASE = dict(Temperature=0.8, TopP=0.95, TopK=1000, RepetitionPenalty=1.2, ReferenceClip="chr_0200.wav")
ORIGINAL_BASE = dict(Temperature=0.8, TopP=1.0, MinP=0.05, RepetitionPenalty=1.2, CFGWeight=0.5,
                     Exaggeration=0.5, ReferenceClip="chr_0200.wav")
RVC_BASE = dict(ConversionStrength=0.75, Protect=0.33, RmsMix=0.25)

REFERENCE_NOTES = {
    "chr_0200.wav": "reflective, measured (baseline reference)",
    "chr_0196.wav": "bright and cheerful, ends on an exclamation",
    "chr_0198.wav": "slow, wistful storytelling",
    "chr_0169.wav": "flat counting (one to ten)",
    "chr_0204.wav": "plain, earnest explanation",
}


def build_settings() -> list[dict]:
    rows: list[dict] = []

    def add(engine, arm, variable, level, values, baseline=False, notes=""):
        row = dict(SettingID=f"S{len(rows) + 1:02d}", Engine=engine, Arm=arm, VariableTested=variable,
                   LevelLabel=level, IsBaseline=baseline, Notes=notes,
                   Temperature=None, TopP=None, TopK=None, MinP=None, RepetitionPenalty=None,
                   CFGWeight=None, Exaggeration=None, ConversionStrength=None, Protect=None, RmsMix=None,
                   ReferenceClip=None, ReferenceStyle=None)
        row.update(values)
        if row["ReferenceClip"]:
            row["ReferenceStyle"] = REFERENCE_NOTES[row["ReferenceClip"]]
        rows.append(row)

    turbo = "Chatterbox Turbo"
    add(turbo, "baseline", "baseline", "show defaults", TURBO_BASE, True, "Live show settings")
    for t in (0.3, 0.55, 1.05, 1.3, 1.6, 2.0):
        add(turbo, "sampling", "temperature", f"T={t}", {**TURBO_BASE, "Temperature": t})
    for p in (0.3, 0.6, 0.8, 1.0):
        add(turbo, "sampling", "top_p", f"top_p={p}", {**TURBO_BASE, "TopP": p},
            notes="top_p=1.0 disables nucleus filtering; it is the reference for the top_k sweep" if p == 1.0 else "")
    for k in (1, 5, 20, 100):
        add(turbo, "sampling", "top_k", f"top_k={k}", {**TURBO_BASE, "TopP": 1.0, "TopK": k},
            notes="top_p held at 1.0 so top_k is the only active filter" + ("; top_k=1 is greedy decoding" if k == 1 else ""))
    for r in (1.0, 1.1, 1.4, 1.7, 2.0):
        add(turbo, "sampling", "repetition_penalty", f"rep={r}", {**TURBO_BASE, "RepetitionPenalty": r})
    for ref in ("chr_0196.wav", "chr_0198.wav", "chr_0169.wav", "chr_0204.wav"):
        add(turbo, "audio prompt", "reference clip", ref.replace(".wav", ""), {**TURBO_BASE, "ReferenceClip": ref})

    orig = "Chatterbox (original)"
    add(orig, "guidance", "baseline", "cfg=0.5 exag=0.5", ORIGINAL_BASE, True, "Original model defaults")
    for c in (0.0, 0.25, 0.75, 1.0):
        add(orig, "guidance", "cfg_weight", f"cfg={c}", {**ORIGINAL_BASE, "CFGWeight": c},
            notes="cfg=0 turns classifier-free guidance off (run as 1e-6: this chatterbox version always samples a CFG batch, and 1e-6 makes the guided logits equal the conditional ones)" if c == 0.0 else "")
    for e in (0.25, 0.75, 1.0, 1.5, 2.0):
        add(orig, "guidance", "exaggeration", f"exag={e}", {**ORIGINAL_BASE, "Exaggeration": e})

    rvc = "Kokoro + RVC"
    add(rvc, "conversion", "control (no conversion)", "Kokoro only", {"ConversionStrength": None},
        notes="Source speaker (Kokoro am_puck) before any conversion")
    for s in (0.0, 0.25, 0.5, 1.0):
        add(rvc, "conversion", "conversion strength (index_rate)", f"index={s}", {**RVC_BASE, "ConversionStrength": s})
    add(rvc, "conversion", "baseline", "index=0.75", RVC_BASE, True, "Former show settings")
    for pr in (0.1, 0.5):
        add(rvc, "conversion", "protect", f"protect={pr}", {**RVC_BASE, "Protect": pr},
            notes="Lower protect converts breaths and consonants too; 0.5 disables protection")
    for m in (0.0, 1.0):
        add(rvc, "conversion", "rms_mix_rate", f"rms={m}", {**RVC_BASE, "RmsMix": m},
            notes="0 keeps the source loudness envelope, 1 uses the converted voice's own")
    return rows


# ------------------------------------------------------------------- plan --

def build_plan(prompts: list[dict], settings: list[dict]) -> list[dict]:
    plan = []
    sweep = [p for p in prompts if p["Arm"] == "parameter sweep line"]
    for s in settings:
        for p in sweep:
            plan.append(dict(StudyBlock="parameter sweep", SettingID=s["SettingID"], PromptID=p["PromptID"], Seed=COMMON_SEED))
    base = settings[0]["SettingID"]
    for p in sweep:
        for seed in SEED_BLOCK:
            plan.append(dict(StudyBlock="seed only", SettingID=base, PromptID=p["PromptID"], Seed=seed))
    for p in prompts:
        if p["Arm"] == "prompt manipulation":
            plan.append(dict(StudyBlock="prompt manipulation", SettingID=base, PromptID=p["PromptID"], Seed=COMMON_SEED))
    for i, row in enumerate(plan, 1):
        row["ClipID"] = f"C{i:03d}"
        row["FileName"] = f"{row['ClipID']}_{row['SettingID']}_{row['PromptID']}_{row['Seed']}.wav"
    return plan


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    prompts = build_prompts()
    settings = build_settings()
    plan = build_plan(prompts, settings)
    write_csv(DATA / "prompts.csv", prompts)
    write_csv(DATA / "settings.csv", settings)
    write_csv(DATA / "plan.csv", plan)
    print(f"{len(prompts)} prompts, {len(settings)} settings, {len(plan)} planned clips")
