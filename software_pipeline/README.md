# Pinocchio AI model pipeline

This is the hardware-free first version of the show-control pipeline.

```text
typed question
      |
      v
local Ollama model (optional)
      |
      v
validated response JSON
      |
      +--> spoken_text -> Chatterbox cloned voice
      +--> truth_tag   -> nose behavior
      +--> motion      -> virtual actuators now / real controller later
      +--> next_state  -> show state machine
```

## Computer-specific paths (machine.json)

Every folder that differs between computers lives in `machine.json`: the voice
runtime (venv, caches, reply WAVs), Ollama, and the voice training corpus. Each
entry under `paths` is either absolute or relative to
`root`. This workshop PC uses absolute paths to its existing `E:` and `Z:`
folders. On a new computer, copy `machine.example.json` to `machine.json` and
set only `root`; the Python code (`machine_paths.py`) and the PowerShell
launchers (`machine_paths.ps1`) resolve paths the same way.

The two `Modelfile`s are only used when rebuilding the Ollama models; point
their `FROM` line at the GGUF file on that computer before running
`ollama create`.

## Run immediately with no model

From PowerShell, in this `software_pipeline` folder:

```powershell
python .\pipeline.py
```

This uses the deterministic truth/lie/confession response bank. Try:

```text
What did you build today?
Tell me the truth.
Please confess.
```

Every turn is logged to `runs.jsonl` so you can replay and test behavior.

## Add a local model later

1. Install Ollama for Windows.
2. Download one local model that your computer can run.
3. Start the same program with the model name:

```powershell
python .\pipeline.py --model <installed-model-name>
```

The program sends a JSON schema to Ollama and rejects any response that does
not match the contract. That keeps the model from sending arbitrary hardware
commands.

## Installed local model

This computer now has `pinocchio-ai`, a local Qwen 2.5 3B model registered in
Ollama. Run the live model pipeline with:

```powershell
.\run_local_ai.ps1
```

For a repeatable judge demonstration, choose the outcome yourself:

```powershell
.\run_local_ai.ps1 --force-tag LIE
```

The AI writes the dialogue, but the validated truth tag controls the nose. That
makes a planned lie, truth, or confession repeatable even when the wording varies.

## Add microphone input and a spoken response

Run the one-time setup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_voice_pipeline.ps1
```

Then run the offline voice loop:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_voice_pipeline.ps1
```

Press Enter to start recording. The program listens for speech, stops after a
short pause, transcribes the question, generates a validated response, writes a
WAV file with Chatterbox, and plays it through the default speaker. Run with
`--list-devices` if Windows chooses the wrong microphone. Put the desired input
device number in `audio_config.json` as `input_device` if needed. It is
preconfigured for the detected Scarlett 2i2 microphone (device `3`).

The installed Whisper `base.en` recognizer is fully local. This computer is now
configured for GPU speech recognition: Whisper uses CUDA `float16`, and
Chatterbox runs on the RTX 5080. The text model also runs on the RTX.

To repeat the acceleration install after rebuilding the voice environment, run:

```powershell
.\setup_gpu_acceleration.ps1
```

## Pinocchio character voice (Chatterbox)

Chatterbox Turbo is the active local voice engine. It clones the character
directly from `wavs/chr_0201.wav` under the `voice_training` folder configured
in `machine.json`. That reference is a clean ten-second recording from the
existing corpus. It is encoded once when the show starts and reused for every
reply; Kokoro and RVC are no longer part of the active synthesis path.

The one-time setup downloads Chatterbox into the existing voice environment and
warms its model cache. Normal launch scripts then force Hugging Face offline
mode, so visitor text and audio remain on this computer.

Tuning keys in `audio_config.json`:

- `chatterbox_reference`: absolute path or path relative to `voice_training`.
- `chatterbox_temperature`, `top_p`, `top_k`, and `repetition_penalty`: Turbo
  sampling controls retained at the official defaults.
- `chatterbox_seed`: fixed positive value for repeatable competition output;
  use `0` for random variation.

Turbo is used because the original 500M expressive model stalled during a real
CUDA smoke test on this Windows/RTX 5080 stack. Turbo uses the same reference
voice, has much lower latency, and supports explicit paralinguistic tags such as
`[chuckle]`, `[laugh]`, `[gasp]`, and `[sigh]`. It does not implement the
original model's exaggeration or CFG sliders.

### Faster synthesis (CUDA graph)

Stock Chatterbox Turbo generates speech tokens one at a time from Python and is
limited by kernel-launch overhead, not by the GPU. `t3_cuda_graph.py` replays
each token step as a CUDA graph instead: on the RTX 5080 that is 43 -> 305
tokens/s and roughly 3x faster synthesis (a short clause in ~0.35 s instead of
~0.9 s), with intelligibility unchanged in a 40-clip Whisper comparison. At
start-up it checks itself against stock decoding and falls back to stock if
anything differs, so the status line shows either `CUDA graph bfloat16` or
`stock decoding`. Seeds still repeat exactly. Keys in `audio_config.json`:

- `chatterbox_cuda_graph`: `false` returns to stock decoding.
- `chatterbox_bf16`: `false` keeps the graph in fp32 (about 30% slower).

## Streaming speech and the two-GPU show PC

With `stream_speech` on (the default), the control panel speaks a reply clause
by clause while the model is still writing it, and plays it through this PC's
speakers (the browser keeps it for replay). The first clause is kept short so
speech starts fast; later clauses are sized to what the voice can synthesize
before the audio already queued runs out, so there are no silent gaps.
`stream_first_chunk_words` sets how soon the first clause leaves without
punctuation; `output_device` picks the speaker (see `--list-devices`).

The show PC splits the work across two cards: Ollama on the RTX 2060 (6 GB) and
Whisper plus Chatterbox on the RTX 3070 (8 GB). Name them in `machine.json`:

```json
"gpus": { "text": "2060", "voice": "3070" }
```

The launchers pin each process to its card. Ollama reads the pin only when it
starts, so quit any Ollama that is already running (including its tray icon)
first; the launcher warns if it finds one.

`run_stream_check.ps1` times streamed replies (first text, first audio, gaps
between clauses) and checks VRAM against the 6 GB / 8 GB budgets:

```powershell
.\run_stream_check.ps1                      # real numbers on the show PC
.\run_stream_check.ps1 --simulate-show-pc   # approximate it on one bigger GPU
.\run_stream_check.ps1 --mute "Why do cats purr?"
```

`--simulate-show-pc` (also accepted by `run_ui.ps1`) caps the voice process at
8 GB and slows text 3x and voice 1.8x. Those slowdowns are estimates from
memory bandwidth; replace them in `streaming_speech.py` (`SHOW_PC`) with what
the show PC actually measures.

## Voice benchmark

`run_benchmark.ps1` loads the same stack as the UI (Whisper, the Ollama model,
and the configured voice), then times every line in `eval/test_lines.json`:

```powershell
.\run_benchmark.ps1                      # all test lines
.\run_benchmark.ps1 --questions          # also time question -> AI -> voice turns
.\run_benchmark.ps1 --limit 10 --label quick
```

Each run writes `summary.json`, `results.jsonl`, and every generated WAV to
`benchmarks\<time>-<computer>[-label]` in the runtime folder. The summary holds
synthesis time, real-time factor, peak GPU memory above the pre-load baseline,
voice fallbacks, and a rough intelligibility score (Whisper word error rate on
the generated audio). Run it on each computer and after every voice change so
results stay comparable; the saved WAVs double as blind-listening-test clips.
The benchmark times whole lines; use `run_stream_check.ps1` for time to first
audio with streaming.

## Audio Performance Lab

The lab is reached from the control panel and compares voice *settings*, not
individual clips. One round is laid out as a grid:

- **settings** — a reference recording plus a temperature and a repetition
  penalty (2–4 per round)
- **lines** — your typed line first, then show lines pulled from
  `eval/test_lines.json`, one per category, preferring lines that carry
  paralinguistic tags (2–4 per round)
- **seeds** — the same fixed seeds for every setting (2–4 per round)

Every setting speaks every line at every seed, and you rate the whole group of
takes at once. That is deliberate: at these temperatures the seed moves delivery
about as much as a temperature step does, so a single clip per setting mostly
measures which seed got lucky. Settings × lines is capped at 12 rated groups.

A setting's score is its mean across the lines. The reveal also shows
**spread**, the gap between its best and worst line, because a setting that
nails the greeting and falls apart on the confession is worse for a live show
than a steady one with a lower peak.

Two knobs are treated as fixed rather than swept. `top_k` at 1000 is inert
under `top_p` 0.95, and Turbo ignores `exaggeration`, `cfg_weight` and `min_p`
outright. `repetition_penalty` is swept instead — it is the second live
delivery control and the one that clips or rushes the end of a long line.

Applying a winner writes the reference and the delivery settings to
`audio_config.json` and **leaves `chatterbox_seed` alone**, since the round
judged that setting across seeds on purpose.

## Fast show mode

The normal launch scripts keep the local model warm for 30 minutes, limit it to
short show lines, and use a 0.65-second end-of-speech pause. This reduces the
time between a visitor finishing a question and hearing Pinocchio respond. The
current model remains entirely local and GPU accelerated through Ollama, Whisper,
and Chatterbox.

This computer also has `pinocchio-fast`, a Qwen 2.5 1.5B model for short,
structured show replies. The browser control panel offers **Fast · 1.5B** and
**Quality · 3B (slower)**. Fast is the default. Common visitor questions use a
local response bank for an instant, on-topic answer; open-ended questions use
the selected local model. Both paths use the same controller-owned truth tag,
motion validation, and response contract.

To use Fast mode from the terminal instead, run:

```powershell
.\run_fast_ai.ps1
```

## Use the browser control panel

Run the local UI instead of the terminal voice loop:

```powershell
.\run_ui.ps1
```

It opens `http://127.0.0.1:8787` on this computer. Select **Record question**
to use the Scarlett 2i2 microphone, or type a question to test without speaking.
The panel displays the transcript, the AI response, validated show outcome,
virtual nose position and motion commands, then plays the Chatterbox response. Keep
the PowerShell window open while you use the control panel; press `Ctrl+C` there
when you are finished.

## Test and learn the character's humor

Run the separate, lightweight Humor Lab without loading the voice or AI stack:

```powershell
.\run_humor_lab.ps1
```

It opens `http://127.0.0.1:8788` with 72 shuffled lines and a 1–7 funniness
scale. Ratings remain local and can be exported to CSV. After 12 ratings the
lab can train a small preference reranker; 36 or more ratings are recommended
before using its style suggestions in the live character. See
`humor_lab/README.md` for the experiment and model details.

## Response contract

The model must return:

- `spoken_text`: the line Pinocchio says
- `truth_tag`: `TRUTH`, `LIE`, or `CONFESSION`
- `emotion_intensity`: 0 to 1
- `source_id`: a traceable response-bank/model identifier
- `motion`: bounded virtual actuator commands
- `next_state`: the next show state

Edit `response_schema.json` only when the control team agrees on an interface.
Hardware code should consume this contract; it should not consume raw model
text.

## Voice safety behavior

If no speech is detected or recognition fails, Pinocchio asks the visitor to
repeat the question. The raw language model never gets direct actuator access:
the validated response packet and truth tag still decide each virtual motion.
