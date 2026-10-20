# Voice generation behavioral study

How the delivery of the Pinocchio voice changes when you change the prompt, the
sampling settings (temperature, top-k, top-p, repetition penalty), classifier-free
guidance and exaggeration, the audio reference, and voice-conversion strength.
It covers behavior only (tone, pauses, resonance, breathiness, pacing, word choice);
speed and accuracy scores are left to the performance study.

Results are in [FINDINGS.md](FINDINGS.md). The Access database is
`VoiceBehaviorStudy.accdb`.

## Design

- **Three engines**, all local:
  - Chatterbox Turbo (the live show voice): temperature, top-p, top-k, repetition penalty, audio reference.
  - Original Chatterbox: CFG weight and exaggeration. Turbo ignores both.
  - Kokoro speech converted by the trained RVC Pinocchio model: conversion strength (`index_rate`), `protect` and `rms_mix_rate`.
- **One factor at a time.** Each of the 44 settings changes one knob from its engine's
  baseline. Every setting speaks the same three show lines (greeting, lie,
  confession) with the same seed, so differences come from the knob, not luck.
- **Seed-only block.** The baseline speaks each line with 6 different seeds. This is the
  "noise floor": an effect counts only when it is bigger than the seed-to-seed spread.
- **Prompt arm.** Three base sentences are each rewritten 14 ways (punctuation, CAPS,
  `[sigh]`/`[chuckle]`/`[whispering]`/`[sarcastic]`/`[fear]` tags, written hesitation,
  stretched spelling, a written stage direction) at the baseline setting.
- **Word-choice arm.** The show's language model (`pinocchio-fast`) answers two visitor
  questions with the show's exact prompt under 20 sampling settings each.
- **Blind listening session.** 50 clips are rated by ear with the settings hidden and the
  order shuffled per listener: 44 settings on the confession line plus 6 prompt variants.

That comes to 192 voice clips and 40 written lines. Audio is in `Z:\PinocchioBehaviorStudy\clips`.

## Database (VoiceBehaviorStudy.accdb)

| Table | Records | Fields | One row is |
|---|---|---|---|
| Prompts | 45 | 14 | a text the voice was asked to say |
| ParameterSettings | 44 | 20 | an experimental condition |
| Generations | 192 | 14 | a clip: prompt + setting + words actually heard |
| AcousticBehavior | 192 | 24 | delivery measurements + plain-language labels for a clip |
| ListenerRatings | 50 per listener | 14 | one blind human rating of a clip |
| ScriptVariants | 40 | 24 | a line written by the language model |

Relationships: Generations → ParameterSettings and Prompts; AcousticBehavior and
ListenerRatings → Generations. Every field has a description, visible in Access Design View.

Saved queries (open them from the Access navigation pane):

| Query | Answers |
|---|---|
| qrySilencesAndListenerFlags | Which settings made silences over 1 s, and did the listener notice? |
| qryPromptWordChanges | Which prompt rewrites changed the spoken words? |
| qryListenerVsMeasures | Listener ratings next to the matching measurements, clip by clip |
| qryRatingsByEngine | Average listener ratings per engine |
| qryScriptOverlap | How far each language-model line moves from its baseline wording |

## Re-running

From this folder, using the voice environment's Python (`E:\PinocchioAudio\venv\Scripts\python.exe`):

```text
python design.py                     # plan -> data/*.csv
python generate.py --engine turbo    # also: --engine original, --engine rvc
python analyze.py                    # acoustics + transcripts
python script_variants.py            # language-model word choice
python listen/server.py              # listening session at http://127.0.0.1:8790
python export_tables.py              # -> db_tables/*.csv
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_database.ps1
```

`build_database.ps1` replaces the .accdb each time, so re-run the last two steps
after anyone new does the listening session.

## How the behavioral measures are made

All measures cover only the spoken part of a clip. Anything after the last word is
described separately as `EndingBehavior`.

- **Tonality.** Pitch range in semitones (pYIN pitch tracker), plus the intonation contour of the line ending.
- **Pauses.** Silent gaps of 150 ms or more inside the line.
- **Formants and resonance.** F1/F2 from LPC on voiced frames; spectral centroid for brightness.
- **Volume.** Median level and loud-to-soft range.
- **Breathiness.** Harmonics-to-noise ratio (lower is breathier or rougher).
- **Pacing.** Syllables per second of actual speaking time.
- **Words.** Whisper `base.en` transcript compared with the intended words. Each clip is coded faithful, dropped, added, repeated, substituted, or "read cue aloud".

Plain-language labels (e.g. "breathy/rough", "rushed") split the whole study into
thirds, so they describe each clip *relative to the others*.
