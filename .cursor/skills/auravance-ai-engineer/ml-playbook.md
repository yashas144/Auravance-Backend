# Auravance ML playbook

Read this before training, swapping algorithms, or changing scoring.

## Tasks (keep them separate)

1. **Anomaly** — Isolation Forest, unsupervised on healthy operation.
2. **Failure** — P(failing now or within 72h). Classifier, calibrated.
3. **RUL** — hours until next failure, capped (pump: 240h, 0 while down).

Do not reuse a classification score as RUL without an explicit mapping (the
compressor sudden-failure wrappers are the allowed exception).

## What is actually trained

| Profile | Algorithm in artifacts | Scripts |
|---|---|---|
| pump anomaly | Isolation Forest | `scripts/train_anomaly_model.py` |
| pump failure / RUL | `HistGradientBoostingClassifier` / `Regressor` | `train_failure_model.py`, `train_rul_model.py` |
| compressor, motor | same family, per-profile | `train_profile_models.py compressor\|motor` |

XGBoost is a runtime dependency and is served when `*_xgboost.joblib`
artifacts exist; otherwise HistGradientBoosting artifacts stay in front.
LSTM is optional (`pip install -e ".[sequence]"`) and served beside
tabular models when `*_failure_lstm.joblib` is present. Do not describe
LSTM as live if torch or the sequence artifact is missing.

Shared feature transform: four channels, `runtime_profile` center/scale stored
in the artifact so live telemetry matches training. Pump channels are
anonymized in the source CSV and rescaled with the anomaly model's transform.

## Artifact schema

joblib dict, `artifact_schema_version: 1`. Required ideas:

- `task`, `model_version`, `algorithm`, `trained_at`, `source_dataset`
- `feature_names` subset of `{temperature, vibration, pressure, current}`
- `runtime_profile`, `source_columns`, `source_transform`
- `metrics` (leave-one-failure-out)
- `estimator` (and `fold_models` for honest replay)
- `fold_dataset` matching `source_context.dataset`

Write a sibling `.json` metadata file (estimator stripped) next to the
`.joblib`. Serving loads joblib; humans and `GET /predictions/models/status`
read metadata.

Custom pickle classes (`SuddenFailureClassifier`, `SuddenFailureLifeRegressor`)
live in `app/services/ml_estimators.py` so the API process can unpickle them.

## Evaluation rules

- **Leave-one-failure-out.** Each failure cycle is scored by a model trained
  without it. Store those metrics; do not report only in-sample accuracy.
- **Held-out serving.** `prognostics._select_estimator` uses `fold_models`
  when `source_context.dataset == fold_dataset` and `source_timestamp` falls
  in a held-out window. Tests in `test_prognostics_models.py` lock this in.
- **No class weighting** on the failure classifier — keep probabilities
  closer to calibrated.
- **Label scarcity is normal.** Pump: 7 failures. Compressor: 4 leaks. Motor:
  3 run-to-failure tests. Do not invent synthetic labels to juice AUC.
- **Document failure physics.** Compressor leaks are sudden (hours before a
  leak look healthy; 72h forecast is not learnable). Motor bearings degrade.
  Pump 72h warning is only present for some events. Put limits in metadata
  `notes` / README, not in marketing comments.

Published honest numbers (update JSON if you retrain, then README):

- Pump failure LOO AUC ~0.66; P(fail) ~0.89 down vs ~0.14 healthy.
- Pump RUL MAE ~64h vs ~81h constant guess.
- Compressor anomaly AUC ~0.99; leak-now AUC ~0.96; 72h forecast AUC ~0.45
  (not used — sudden wrapper + 6% base rate).
- Motor anomaly AUC ~0.98; P(fail) climbs 0.22 healthy → 0.78 last 24h.

A "30% detection accuracy" claim is **not** in the training scripts. If asked
to support that north-star bullet, define a baseline (rules scorer), measure
on the same LOO splits, and record the delta in artifact metrics.

## Serving

`app/services/scoring.py`:

1. Load profile models via `models_for(profile_for_asset(asset_id))`.
2. Anomaly model if loaded, else rules mix of normalized channels + trend bonus.
3. Failure / RUL models if loaded, else derive from anomaly/rules.
4. Dominant signal from model deviations, else rules (including
   `pressure_instability` and `bearing_pattern` heuristics).

Model load failures must not crash the API. Status endpoints expose
`fallback_active` and `detail`.

## Training commands

From repo root, after datasets exist:

```bash
python scripts/train_anomaly_model.py
python scripts/train_failure_model.py
python scripts/train_rul_model.py
python scripts/train_profile_models.py compressor
python scripts/train_profile_models.py motor
```

Dataset prep (raw archives are gitignored):

```bash
python scripts/prepare_datasets.py
python scripts/build_replay_dataset.py
python scripts/prepare_metropt.py
python scripts/prepare_ims.py
```

Restart uvicorn after writing artifacts.

## Adding XGBoost

- Add `xgboost` to `pyproject.toml`.
- Keep `artifact_schema_version: 1` and the same `feature_names` /
  `runtime_profile` so `FailureModelService` / `RulModelService` stay valid.
- Re-run LOO evaluation; compare to current HGB metrics in the JSON sidecar.
- Do not delete HGB artifacts until the new models load and tests pass.

## Adding LSTM

- Needs windowed sequences, not the current single-row transform.
- New artifact task (e.g. `failure_sequence`) and a parallel service; tabular
  models remain the fallback.
- Do not require PyTorch/TF at API import time — lazy-import like joblib in
  `AnomalyModelService._load`.
- Train only when sequence history is real (replay/IMS windows), not on three
  synthetic points from the dashboard.

## Tests to touch

- `tests/test_anomaly_model.py`
- `tests/test_prognostics_models.py` (held-out versions, state tracking)
- `tests/test_equipment_profiles.py`
- `tests/test_pump_replay.py`
- `tests/test_telemetry_ingest.py`
