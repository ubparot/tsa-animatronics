# Findings: how generation settings change the voice's behavior

192 clips from three local voice engines and 40 lines from the show's language model,
analyzed for tone, pauses, resonance, volume, breathiness, pacing and word choice.
Numbers are averages over the three sweep lines unless noted. See [README.md](README.md)
for the method.

## The noise floor comes first

With every setting fixed and only the seed changed, the baseline voice still moved:

| Measure | Seed-to-seed spread (SD) |
|---|---|
| Mean pitch | about ±11 Hz |
| Pitch range (melody) | ±0.8 to 2.1 semitones |
| Brightness (spectral centroid) | ±47 to 74 Hz |
| Breathiness (HNR) | ±0.4 to 0.8 dB |

The seed also changed words. In 4 of 18 seed-only clips the voice said something
different, for example "I don't bite" became "I **do** bite!" (seed 44444), and the same
seed made the whole greeting exclaimed. **A single clip per setting therefore says little.**
Only effects well beyond these spreads are reported below as real.

## Sampling settings (Chatterbox Turbo)

**Temperature mostly controls whether the words survive, not the tone.**
- From 0.55 to 1.3, pitch, melody and breathiness stay inside the noise floor.
- At 1.6 and 2.0 the voice starts inventing words while keeping a confident, fluent delivery: "the king of a tiny kingdom" became "king of a teleking noodle", and "I'm made of wood" became "I need to move it". Melody widens (12 → 15 semitones) and pacing slows (5.5 → 4.4 syllables/s).
- 10 of 18 temperature clips had altered words. All six at 1.6 and 2.0 contained invented phrases; those between 0.55 and 1.3 were single-word slips such as "I'm" heard as "I".

**Too little randomness makes the voice freeze.**
- Restricted sampling (temperature 0.3, top-k 1, or top-p 0.8 and below) kept the words but inserted **1.8 to 11.9 seconds of dead silence** at sentence breaks. No seed-only clip paused longer than 0.8 s, and the one-sentence lie line never got these silences. At top-p 0.8 the silence appeared only in the confession.
- The 3.4-second confession line ran 15 seconds at temperature 0.3, then came out garbled after the gap ("I want to have killing you").
- So "safe" low-randomness settings are not safe for a live show: the model stalls at punctuation instead of moving on.

**Top-k barely matters in the normal range; top-p matters more than expected.**
- Top-k from 5 to 1000 and top-p 1.0 kept delivery within the noise floor.
- Top-p already causes silences at 0.8 (see above). Keep it above 0.8; the show's 0.95 is fine.
- Under the show's top-p of 0.95, top-k 1000 is inert, as the pipeline README already notes.

**Repetition penalty saturates.**
- Penalties 1.7 and 2.0 produced **byte-identical audio** on all three lines. By 1.7, every recently used speech token is already pushed out of the top-p nucleus, so raising it further changes nothing.
- At 1.0 (no penalty) pitch sat about 20 Hz lower than at 1.2 to 2.0.
- Penalties of 1.4 and above dropped a syllable from the greeting ("I'm made of wood" heard as "I made wood").

## Audio prompt (the reference clip): the strongest delivery control

Changing only the 10-second reference recording moved the voice more than any sampling knob:

| Reference clip | Its style | Mean pitch | Pitch range | Pacing |
|---|---|---|---|---|
| chr_0200 (baseline) | reflective | 298 Hz | 11.9 st | 5.5 syl/s |
| chr_0196 | bright, exclaiming | **411 Hz** | **14.8 st** | 4.9 |
| chr_0169 | flat counting | **405 Hz** | 13.0 st | **4.6** |
| chr_0204 | plain, earnest | 336 Hz | **15.3 st** | 5.1 |
| chr_0198 | slow storytelling | 299 Hz | 10.1 st | 5.2 |

- The model copies the *energy and register* of the reference, not its literal style.
- The counting clip produced a high, open-mouthed voice (F1 688 Hz vs 575 Hz baseline) rather than a flat one.

## Classifier-free guidance and exaggeration (original Chatterbox)

**CFG weight changed little in delivery.**
- From 0 to 1.0, pitch, melody and breathiness stayed within the noise floor.
- Lower CFG (0 to 0.25) slowed pacing slightly (4.3 to 4.5 vs 4.9 to 5.0 syllables/s), and the one CFG word error happened at 0.25 ("tiny" heard as "timey").
- In this model CFG mainly keeps the speech tied to the *text*, not to the emotion.

**Exaggeration is a strong, nearly linear "intensity" dial, and past 1.0 it breaks.**

| Exaggeration | Mean pitch | Behavior |
|---|---|---|
| 0.25 | 260 Hz | calm, low |
| 0.5 (default) | 272 Hz | baseline |
| 1.0 | 331 Hz | animated |
| 1.5 | 445 Hz | every sentence exclaimed, more pauses, mouth opens wider (F1 729 Hz) |
| 2.0 | 437 Hz | shouting, slow (3.8 syl/s); invents outbursts |

At 2.0 the voice added words that were never in the script: "**Dying!** I'm sorry!",
"**DUMB!** Of course!", "**No!** A visitor!". Altered words appeared in 6 of 15
exaggeration clips, against 0 of 3 at the default.

## Voice conversion strength (Kokoro → RVC)

**Conversion changes *who* is speaking, not *how* they speak.**
- Converting Kokoro's adult voice to the Pinocchio model moved pitch from 119 Hz to about 344 Hz and brightness from 1,010 Hz to about 1,880 Hz.
- Pacing (6.2 syllables/s), pause pattern (none) and intonation contour (falling on all three lines) stayed exactly as Kokoro delivered them.
- Across `index_rate` 0 to 1.0, every delivery measure stayed within a few percent. The trained model already stamps the timbre at 0, and the retrieval index adds little on top.
- `protect` and `rms_mix_rate` also left delivery unchanged. RVC never altered a word (0 of 30 clips).
- So the source speaker's *behavior* survives conversion at any strength. Only pitch and timbre are replaced.
- To change how the converted voice acts, change the source speech, not the conversion strength.
- Kokoro + RVC delivered the most even, unpaused lines in the study (rated "no internal pauses" on all 30 clips), which is part of why it can sound read rather than performed.

## Prompt wording (Chatterbox Turbo)

| Rewrite | What the voice did |
|---|---|
| Question mark | Ending rose on all 3 sentences, even when the sentence was not a question |
| Ellipsis `...` / extra commas | Added 1 to 2 internal pauses and slowed pacing (5.2 → 4.2 syl/s with commas). Reliable phrasing control |
| Exclamation mark | Slightly higher pitch (+30 Hz), no added melody |
| CAPS on a word | **Spelled out letter by letter** in the confession ("B-E-D", noticed by the listener; Whisper wrote it as a capitalized "BED"). No pause and a flat melody (8.1 st) |
| `[sigh]` | An audible "huh" exhale on all 3 sentences, then a flatter line |
| `[chuckle]` | Widest melody in the arm (13.4 st) and the brightest sound: the laugh carries into the words |
| `[whispering]` | Not spoken aloud. Flatter melody (8.8 st). No measured breathiness increase, but the listener heard it as whispery (breathiness 4 of 5) |
| `[sarcastic]` | Flattest of all (7.1 st), a dry monotone, but nothing clearly sarcastic in the measurements |
| `[fear]` | Melody wider than plain (12.5 vs 10.3 st). No pauses or shakiness detected |
| Written "I-I ... um" | The model **smoothed it away**: the "um" was dropped in all 3 sentences and the stutter in 2 |
| Stretched spelling "neeever", "beeed" | Pronounced as a normal or different word ("bead") instead of a drawn-out vowel |
| "(whispering)" written in parentheses | **Read aloud as the word "Whispering"** on all 3 sentences. Only bracket tags are acted out |

Paralinguistic tags in square brackets are performed. Stage directions in
parentheses and spelled-out hesitations are not.

## Word choice and phrasing (language model, `pinocchio-fast`)

- **Low randomness gives generic and repetitive lines.** At temperature 0 (identical to top-k 1) the model gave a believable breakfast instead of the requested playful lie, and repeated "big". Top-p 0.3 produced "a big, juicy carrot and a big, juicy carrot stick".
- **The normal range converges.** In 10 of the 12 top-p and top-k settings away from the greedy end (top-p 0.6 to 1.0, top-k 5 to 1000), the model returned the baseline line or a trimmed copy of it. Around the show defaults, top-p and top-k hardly change the words at all.
- **High temperature drifts off-task before it becomes nonsense.** At 1.1 and above the model dodged the question ("I don't know, dear visitor..."), refused the confession and kept lying ("I did indeed make my own house"), or turned surreal ("My breakfast was just my bed").
- **The seed matters as much as any knob.** One seed looped "I had a big breakfast today!" three times. Another seed turned the requested confession into the opposite ("Yes, I built this whole workshop by myself").
- **The 108-character schema limit cuts lines mid-word.** 15 of 40 lines ended mid-sentence ("my friends, like Ge-"). Long, earnest confessions were cut most often, so the limit shapes phrasing toward short, punchy lines.
- **30 of 40 lines opened with "Well,"** and 3 more with "Oh,", even though the show prompt asks the model to "Start directly with the answer." Only high temperature or a new seed broke the habit. This is the model's strongest phrasing default, and it overrides the instruction.

## Corrections to the study premise

A few statements in the original study description don't match how these models work.
Suggested wording:

- **CFG** exists only in the original Chatterbox. Turbo (the live show voice) ignores `cfg_weight` and `exaggeration`. In our results CFG changed text adherence more than tone.
- **Top-k / top-p** filter *speech tokens* (25 per second, from a learned audio codec), not phonemes.
- **Conversion strength.** In RVC, timbre comes from the trained model at every setting. `index_rate` only blends in retrieved features from the training voice. Describe it as how strongly the target's articulation features are retrieved, not as how much timbre is stamped over the source. Our data shows it barely changes behavior.
- **Exaggeration** is the parameter that most directly controls emotional intensity. It deserves its own line in the description.

## Limitations

- **One seed per setting.** Small effects are inside the noise floor and are not interpreted.
- **Recognizer limits.** Transcripts come from Whisper `base.en`, which cannot spell "Geppetto" (its usual misspellings are mapped back) and sometimes mishears "hid" as "hit". Treat single-word substitutions as possible recognizer errors.
- **Recognizer hallucinations.** Whisper sometimes invented a repeat of the whole line. Five such repeats were discarded because the clips were normal length; a real repeat would nearly double it. No clip actually repeated a line.
- **Relative labels.** The labels split this study into thirds; they are not absolute norms.
- **Pitch shift.** The RVC pitch shift (+19 semitones) was measured from the median pitch of the character corpus, not tuned by ear.
- **One listener.** All 50 ratings come from one listener (the author), blind to each clip's setting but not to the study's purpose.
- **Breathiness measure.** HNR did not match perceived breathiness (rank correlation .02).

## Listener ratings

One listener rated 50 clips blind (settings hidden, order shuffled): the confession line from all 44 settings plus 6 prompt variants.

**The ear and the measurements agree on concrete events.**

| Listener judgment | Measurement | Result |
|---|---|---|
| "Long silence" flag | Internal pause > 1 s | Flagged on exactly the 5 clips with such a pause, no others |
| Pacing | Syllables per second | rank correlation .54 (p < .001); all 10 Kokoro clips judged "too fast" |
| Expressiveness | Mean pitch / pitch range | .60 (p < .001) / .42 (p = .002) |
| Expressiveness | Loudness range | .09 (no relation) |
| Breathiness | HNR | .02 (no relation; HNR misses perceived breathiness) |
| "Wrong words" flag | Words differed from script | 4 of 7 altered clips flagged |
| Hidden repeat (rep 1.7 and 2.0 are identical audio) | Same clip rated twice | Same on 4 of 8 judgments, 3 within one point, pacing differed |

The p values come from 20,000 permutations.

**Ratings by group** (1–5 scales):

| Group | Clips | Match | Expr. | Nat. | Artic. | Fit | Most common tone |
|---|---|---|---|---|---|---|---|
| Turbo: sampling + baseline | 20 | 3.3 | 3.1 | 3.2 | 3.9 | 3.2 | remorseful (11) |
| Turbo: reference recordings | 4 | 2.8 | 4.0 | 2.5 | 3.0 | 2.8 | cheerful (2) |
| Original: CFG + baseline | 5 | 3.8 | 3.4 | 4.4 | 4.6 | 4.4 | remorseful (4) |
| Original: exaggeration | 5 | 3.2 | 4.2 | 4.2 | 4.6 | 4.4 | remorseful (2) |
| Kokoro, no conversion | 1 | 4.0 | 3.0 | 4.0 | 4.0 | 1.0 | remorseful |
| Kokoro + RVC conversions | 9 | 2.6 | 4.1 | 3.8 | 3.6 | 3.9 | excited (6) |
| Prompt modifications | 6 | 1.8 | 3.0 | 4.2 | 4.2 | 3.7 | warm (4) |

**What the listener heard that the measurements missed:**
- **The original Chatterbox sounds best.** CFG 0.75 and 1.0 were the only clips rated 5 on match, naturalness, articulation and fit together; the listener's notes called them "perfect" and "amazing".
- **Low repetition penalty sounds robotic.** Penalties 1.0 and 1.1 were heard as flat/robotic (naturalness 2). Penalties of 1.4 and above were heard as remorseful (naturalness 3–4). The acoustics had these within noise.
- **Conversion changes the perceived emotion.** Kokoro alone was heard as remorseful but "hella deep" (character fit 1). All 9 converted clips were heard as excited, cheerful or whispery, never remorseful. The +19 semitone shift reads as excitement even though timing is untouched.
- **Exaggeration fools the ear.** Exaggeration 1.0 and 2.0 got the maximum character fit, and the invented "Dying!" was not flagged as a wrong word. Exaggeration 1.5 was flagged for shouting and audio clipping.
- **Reference swaps hurt naturalness.** This group had the lowest naturalness (2.5). The counting reference was rated 1 on naturalness and match and flagged as metallic.
- **Prompt rewrites missed the intended emotion.** Match averaged 1.8, and the clips were mostly heard as warm rather than remorseful. `[whispering]` was heard as whispery.
