# Pinocchio Humor Lab

A local, dependency-free rating experiment for deciding which Pinocchio joke
styles are actually funny to the production team.

## Run it

From the `software_pipeline` folder:

```powershell
.\run_humor_lab.ps1
```

The browser opens at `http://127.0.0.1:8788`. Use number keys `1` through `7`
to rate quickly. The 72 lines are shuffled separately for each rating profile,
and joke labels remain hidden during the experiment.

Ratings are append-only in `data/ratings.jsonl`; editing a score creates a new
event and the latest value is used. The UI can export the current ratings to
CSV at any time.

## What training means

After at least 12 ratings, **Train preference model** writes:

- `data/humor_model.json`: an interpretable ridge reranker and aggregated
  preference estimates;
- `data/prompt_preferences.txt`: a compact preference summary for the local
  dialogue model.

The regular `pipeline.py` automatically adds that preference summary to its
system prompt when the file exists. Until you press the training button, the
live character behaves exactly as before.

This does not fine-tune Chatterbox. Chatterbox performs a selected line; the
humor model helps select and prompt the writing. With a small personal dataset,
that is both more reliable and much cheaper than fine-tuning a language model.

For a useful first model, rate at least 36 lines. Rating all 72 gives every joke
device multiple observations and includes eight intentionally straight control
lines. Additional people can select **Start a separate rating profile** so their
judgments remain distinguishable.

The trainer can also run directly:

```powershell
python .\humor_lab\trainer.py
```
