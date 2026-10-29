"""Train LSTM failure-sequence models on replay/processed windows.

Tabular XGBoost/HGB stay as the serving fallback. Torch is required to train.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.model_profiles import artifact_paths  # noqa: E402
from app.services.sequence import build_lstm, numpy_state  # noqa: E402
from local_training_data import FAILURE_STRATEGY, LOADERS, failure_target  # noqa: E402


HIDDEN_SIZE = 16
NUM_LAYERS = 1
EPOCHS = 12
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
STRIDE = 3


def sequence_path(profile: str) -> Path:
    return artifact_paths(profile)["sequence"]


def iter_windows(features: np.ndarray, labels: np.ndarray, timestamps: np.ndarray, groups: np.ndarray, window: int, stride: int):
    for group in np.unique(groups):
        indexes = np.flatnonzero(groups == group)
        if len(indexes) < window:
            continue
        for offset in range(0, len(indexes) - window + 1, stride):
            chosen = indexes[offset : offset + window]
            yield features[chosen], int(labels[chosen[-1]]), str(timestamps[chosen[0]]), str(timestamps[chosen[-1]]), int(group)


def _train_one(windows: np.ndarray, labels: np.ndarray, n_features: int):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    model = build_lstm(n_features, HIDDEN_SIZE, NUM_LAYERS)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.BCELoss()
    loader = DataLoader(
        TensorDataset(torch.tensor(windows, dtype=torch.float32), torch.tensor(labels, dtype=torch.float32)),
        batch_size=min(BATCH_SIZE, max(8, len(windows))),
        shuffle=True,
    )
    model.train()
    for _ in range(EPOCHS):
        for batch_x, batch_y in loader:
            optimizer.zero_grad()
            predicted = model(batch_x)
            loss = criterion(predicted, batch_y)
            loss.backward()
            optimizer.step()
    model.eval()
    return model


def _predict(model, windows: np.ndarray) -> np.ndarray:
    import torch

    if len(windows) == 0:
        return np.array([], dtype=np.float64)
    model.eval()
    with torch.no_grad():
        return model(torch.tensor(windows, dtype=torch.float32)).cpu().numpy()


def train_profile(profile: str) -> dict[str, object]:
    try:
        import torch  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit("PyTorch is required to train LSTM models. pip install -e '.[sequence]'") from exc

    data = LOADERS[profile]()
    window = int(settings.sequence_window_size)
    labels = failure_target(data)
    packed = list(iter_windows(data.features, labels, data.timestamps, data.group, window, STRIDE))
    if len(packed) < 40:
        raise SystemExit(f"Not enough sequence windows to train {profile} LSTM.")
    windows = np.stack([item[0] for item in packed])
    window_labels = np.asarray([item[1] for item in packed], dtype=np.int32)
    window_groups = np.asarray([item[4] for item in packed], dtype=int)
    start_times = [item[2] for item in packed]
    end_times = [item[3] for item in packed]

    oof = np.full(len(windows), np.nan)
    folds = []
    for group in np.unique(window_groups):
        held_out = window_groups == group
        train = ~held_out
        if train.sum() < 20 or held_out.sum() == 0:
            continue
        model = _train_one(windows[train], window_labels[train], windows.shape[-1])
        oof[held_out] = _predict(model, windows[held_out])
        folds.append(
            {
                "held_out_start": min(start for start, mask in zip(start_times, held_out) if mask),
                "held_out_end": max(end for end, mask in zip(end_times, held_out) if mask),
                "state_dict": numpy_state(model.state_dict()),
            }
        )

    scored = ~np.isnan(oof)
    metrics = {
        "loo_roc_auc": round(float(roc_auc_score(window_labels[scored], oof[scored])), 4),
        "loo_average_precision": round(float(average_precision_score(window_labels[scored], oof[scored])), 4),
        "positive_rate": round(float(window_labels[scored].mean()), 4),
        "window_size": window,
        "windows": int(len(windows)),
    }
    full_model = _train_one(windows, window_labels, windows.shape[-1])
    artifact = {
        "artifact_schema_version": 1,
        "task": "failure_sequence",
        "profile": profile,
        "model_version": f"failure-lstm-{profile}-v1.0.0",
        "algorithm": "LSTM",
        "strategy": FAILURE_STRATEGY[profile],
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": data.source_dataset,
        "feature_names": data.feature_names,
        "runtime_profile": data.runtime_profile,
        "fold_dataset": data.fold_dataset,
        "window_size": window,
        "hidden_size": HIDDEN_SIZE,
        "num_layers": NUM_LAYERS,
        "metrics": metrics,
        "state_dict": numpy_state(full_model.state_dict()),
        "fold_models": folds,
        "failures": data.failure_times,
    }
    path = sequence_path(profile)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    metadata = {key: value for key, value in artifact.items() if key not in {"state_dict", "fold_models"}}
    metadata["fold_held_out_ranges"] = [[fold["held_out_start"], fold["held_out_end"]] for fold in folds]
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"profile": profile, "artifact": str(path), "metrics": metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", nargs="*", choices=sorted(LOADERS), help="Profiles to train (default: all).")
    args = parser.parse_args()
    profiles = args.profile or list(LOADERS)
    print(json.dumps({profile: train_profile(profile) for profile in profiles}, indent=2))


if __name__ == "__main__":
    main()
