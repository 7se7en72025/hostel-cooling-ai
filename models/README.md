# Saved trained models

These are fitted artifacts, not placeholders.

`comfort_ann.npz` contains the neural network's learned weights and biases plus holdout metadata. `ann_dataset.csv` preserves 2,000 training and 400 test examples, with synthetic provenance. `ann_loss.json` records the training curve. The three inputs are temperature, RH and airspeed; labels represent a declared synthetic generic occupant.

`routine_model.json` contains learned weekday/time activity counts. `routine_dataset.csv` records a 14-day training period and a separate 7-day chronological test period. `routine_validation.json` records accuracy, macro-F1 and the confusion matrix. The application's cold-start source is explicitly a synthetic prior. Consented local observations can update a participant-specific routine estimate.

Regenerate with `python -m hostel_cooling train`. Model weights for the actual Qwen3 transformer are separate large runtime dependencies under `runtime/llm/`, downloaded from an official pinned revision and SHA256 verified by `setup-model`. They are not committed to Git.
