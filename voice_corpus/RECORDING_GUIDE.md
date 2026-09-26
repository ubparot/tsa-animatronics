# Voice Corpus Recording Guide

Target: **45–60 minutes of clean audio** for Piper fine-tuning.

## What to record

Two sources, in this order:

| Source | Count | Approx. time | Purpose |
|---|---|---|---|
| CMU ARCTIC prompts (`arctic_a0001`–`a0593`) | 593 | ~35 min | Phonetic coverage |
| `prompts_character.txt` (this folder) | 210 | ~20 min | Prosody + domain vocabulary |

Download ARCTIC prompts from the CMU Festvox site (`cmuarctic.data`). Free for research and commercial use. If you have time for the full 1,132 ARCTIC set, take it — more coverage is strictly better for open-domain text.

**Do not skip ARCTIC.** The character sentences alone will not give the model enough phonetic spread, and open-domain LLM output will contain words your reader never spoke.

**Do not skip the character sentences either.** A model trained only on flat ARCTIC declaratives produces flat speech. Sections C (boastful) and D (confession) are what make the lie beat land.

## Gear

- **Mic:** cardioid condenser. Audio-Technica AT2020 (~$99) or borrow from the music department. Not the ReSpeaker array — that's for the show, not for training.
- **Pop filter**, or a sock over a coat hanger.
- **Room:** a closet full of hanging clothes. Failing that, a blanket fort over the desk. You want dead, not reverberant.
- **Interface:** any USB audio interface, or a USB mic.

## Capture settings

| Setting | Value |
|---|---|
| Sample rate | 22050 Hz (or record 48 kHz and downsample) |
| Bit depth | 16-bit (or 24-bit and dither down) |
| Channels | Mono |
| Peak level | −6 to −12 dBFS |
| Processing | **None.** No compression, no EQ, no noise reduction, no gate. |

Processing during capture bakes artifacts into the model. Do it all in post, identically across every file.

## Mic technique

- 15–20 cm from the capsule, slightly **off-axis** (aim past the corner of the mouth) to reduce plosives.
- **Mark the floor and the stand.** Same position every session, or the model learns two different rooms.
- Same time of day if you can. Voices change between morning and evening.

## Session protocol

1. One sentence per file. Name it exactly by its ID: `chr_0001.wav`, `arctic_a0001.wav`.
2. Leave 0.3–0.5 s of silence at head and tail. Trim the rest in post.
3. **Read in character**, but keep energy consistent within a section. Don't let section C drift louder as you go.
4. Retake immediately on: mouth click, audible breath inside the phrase, stumble, or a pitch that wanders off the section's register.
5. Cap sessions at **45 minutes**, then rest. Hydrate. Skip dairy beforehand.
6. Record 30 seconds of pure room tone at the start of each session and keep it. You'll want it if you ever need to match takes.

Budget 5–6 hours across three or four sessions to land 60 clean minutes.

## Post-processing

Apply identically to every file:

1. Trim leading/trailing silence to ~0.25 s
2. High-pass filter at 70 Hz
3. Peak-normalize to −3 dBFS (consistent across all files — do not normalize per-file to different targets)
4. Resample to 22050 Hz mono 16-bit if you captured higher

Then run `build_metadata.py` to generate the LJSpeech `metadata.csv` and validate the set.

## Before you start

Get a **signed voice release** from your reader. It's their likeness, it's a school project, and your build log should show it. Include explicit permission to train a speech synthesis model on the recordings and use the synthesized output in the competition entry.

If you hire a VO artist instead ($150–400), the same clause must be in the contract — standard voice-over agreements do not cover AI training, and you have to ask for it in writing.

## Schedule note

Do this in **W1–W4**, not W9–10. Voice recording needs zero hardware and sits entirely off the mechanical critical path. Your current schedule stacks it into the same fortnight as AI integration, which is your tightest window.

## Training

Fine-tune from a pretrained English Piper checkpoint (not from scratch) on Colab's free GPU tier. 2,000–4,000 steps is usually enough on an hour of audio. Export to ONNX for the Jetson.

Once trained, **pre-synthesize the Tier 2 bank and the Tier 3 script with the same model.** Sheet 10 requires one consistent voice across all three tiers — generating the fallbacks with the trained voice satisfies that and costs nothing at runtime.
