"""Train XGBoost failure and RUL models behind artifact schema v1.

Writes new files next to the existing HistGradientBoosting artifacts. Serving
prefers XGBoost when those files exist; HGB remains the fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score
from xgboost import XGBClassifier, XGBRegressor


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.ml_estimators import SuddenFailureClassifier, SuddenFailureLifeRegressor  # noqa: E402
from app.services.model_profiles import artifact_paths  # noqa: E402
from local_training_data import (  # noqa: E402
    FAILURE_HORIZON_HOURS,
    FAILURE_STRATEGY,
    LOADERS,
    RUL_CAP_HOURS,
    buckets,
    failure_target,
    rul_target,
)


RANDOM_STATE = 42
XGB_CLASSIFIER_PARAMS = {
    "n_estimators": 80,
    "max_depth": 3,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 20,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "n_jobs": 1,
    "random_state": RANDOM_STATE,
    "verbosity": 0,
}
XGB_REGRESSOR_PARAMS = {
    "n_estimators": 80,
    "max_depth": 3,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 20,
    "n_jobs": 1,
    "random_state": RANDOM_STATE,
    "verbosity": 0,
}


def xgb_paths(profile: str) -> dict[str, Path]:
    registry = Path(artifact_paths(profile)["anomaly"]).parent
    if profile == "pump":
        return {"failure": registry / "failure_xgboost.joblib", "rul": registry / "rul_xgboost.joblib"}
    return {
        "failure": registry / f"{profile}_failure_xgboost.joblib",
        "rul": registry / f"{profile}_rul_xgboost.joblib",
    }


def save(path: Path, artifact: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, path)
    metadata = {key: value for key, value in artifact.items() if key not in {"estimator", "fold_models"}}
    if "fold_models" in artifact:
        metadata["fold_held_out_ranges"] = [[fold["held_out_start"], fold["held_out_end"]] for fold in artifact["fold_models"]]
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _hgb_metrics(profile: str, task: str) -> dict[str, float]:
    registry = Path(artifact_paths(profile)["anomaly"]).parent
    filename = {
        "pump": {"failure": "failure_gradient_boosting.json", "rul": "rul_gradient_boosting.json"},
        "compressor": {"failure": "compressor_failure_gradient_boosting.json", "rul": "compressor_rul_gradient_boosting.json"},
        "motor": {"failure": "motor_failure_gradient_boosting.json", "rul": "motor_rul_gradient_boosting.json"},
    }[profile][task]
    path = registry / filename
    if not path.exists():
        return {}
    metrics = json.loads(path.read_text(encoding="utf-8")).get("metrics", {})
    cleaned = {}
    for key, value in metrics.items():
        if isinstance(value, (int, float)) and value == value:
            cleaned[f"hgb_{key}"] = float(value)
    return cleaned


def train_profile(profile: str) -> dict[str, object]:
    data = LOADERS[profile]()
    paths = xgb_paths(profile)
    trained_at = datetime.now(timezone.utc).isoformat()
    target = failure_target(data)
    rul = rul_target(data)
    strategy = FAILURE_STRATEGY[profile]
    common = {
        "artifact_schema_version": 1,
        "profile": profile,
        "trained_at": trained_at,
        "source_dataset": data.source_dataset,
        "feature_names": data.feature_names,
        "runtime_profile": data.runtime_profile,
        "failures": data.failure_times,
        "fold_dataset": data.fold_dataset,
        "evaluation": "leave-one-failure-out",
    }

    def make_classifier(train: np.ndarray):
        classifier = XGBClassifier(**XGB_CLASSIFIER_PARAMS)
        if strategy == "sudden":
            in_failure = classifier.fit(data.features[train], data.down[train].astype(int))
            up = train & ~data.down & data.known
            if data.forecast_horizon_hours <= 0 or not up.any():
                base_rate = 0.06
            else:
                base_rate = float(target[up].mean())
            return SuddenFailureClassifier(in_failure, base_rate=base_rate)
        return classifier.fit(data.features[train], target[train])

    def make_regressor(train: np.ndarray):
        if strategy == "sudden":
            in_failure = XGBClassifier(**XGB_CLASSIFIER_PARAMS).fit(data.features[train], data.down[train].astype(int))
            up = train & ~data.down & data.known
            return SuddenFailureLifeRegressor(in_failure, mean_healthy_hours=float(rul[up].mean()) if up.any() else RUL_CAP_HOURS)
        return XGBRegressor(**XGB_REGRESSOR_PARAMS).fit(data.features[train], rul[train])

    def cross_fit(make, predict):
        out_of_fold = np.full(len(data.features), np.nan)
        folds = []
        for group in np.unique(data.group):
            held_out = data.group == group
            train = ~held_out & data.known
            if train.sum() < 20 or held_out.sum() == 0:
                continue
            try:
                estimator = make(train)
            except ValueError:
                continue
            out_of_fold[held_out] = predict(estimator, data.features[held_out])
            times = [str(value) for value in data.timestamps[held_out]]
            folds.append({"held_out_start": min(times), "held_out_end": max(times), "estimator": estimator})
        return out_of_fold, folds

    probabilities, folds = cross_fit(make_classifier, lambda estimator, features: estimator.predict_proba(features)[:, 1])
    scored = data.known & ~np.isnan(probabilities)
    if len(np.unique(target[scored])) < 2:
        failure_auc = None
    else:
        failure_auc = round(float(roc_auc_score(target[scored], probabilities[scored])), 4)
    failure_metrics = {
        "loo_roc_auc": failure_auc,
        "loo_average_precision": round(float(average_precision_score(target[scored], probabilities[scored])), 4),
        "positive_rate": round(float(target[scored].mean()), 4),
        **{
            f"loo_mean_probability_{name}": round(float(np.nanmean(probabilities[mask & scored])), 4)
            for name, mask in buckets(data).items()
            if (mask & scored).any()
        },
        **_hgb_metrics(profile, "failure"),
    }
    save(
        paths["failure"],
        {
            **common,
            "task": "failure_classification",
            "model_version": f"failure-xgb-{profile}-v1.0.0",
            "algorithm": "XGBClassifier",
            "strategy": strategy,
            "target": (
                "failure in progress now"
                if data.forecast_horizon_hours <= 0
                else f"failure in progress now or within {data.forecast_horizon_hours:.0f}h"
            ),
            "notes": (
                "Trained on replay episodes; 72h forecast needs the full processed CSV."
                if data.forecast_horizon_hours <= 0
                else "Leave-one-failure-out on the profile dataset."
            ),
            "metrics": failure_metrics,
            "estimator": make_classifier(data.known.copy()),
            "fold_models": folds,
        },
    )

    predictions, folds = cross_fit(make_regressor, lambda estimator, features: estimator.predict(features))
    scored = data.known & ~np.isnan(predictions)
    clipped = np.clip(predictions, 0, RUL_CAP_HOURS)
    rul_metrics = {
        "loo_mae_hours": round(float(mean_absolute_error(rul[scored], clipped[scored])), 2),
        "constant_baseline_mae_hours": round(
            float(mean_absolute_error(rul[scored], np.full(int(scored.sum()), rul[scored].mean()))), 2
        ),
        **{
            f"loo_mean_prediction_hours_{name}": round(float(clipped[mask & scored].mean()), 1)
            for name, mask in buckets(data).items()
            if (mask & scored).any()
        },
        **_hgb_metrics(profile, "rul"),
    }
    save(
        paths["rul"],
        {
            **common,
            "task": "rul_regression",
            "model_version": f"rul-xgb-{profile}-v1.0.0",
            "algorithm": "XGBRegressor" if strategy == "degradation" else "XGBClassifier",
            "strategy": strategy,
            "target": f"hours until the next failure, capped at {RUL_CAP_HOURS:.0f}h; 0 during a failure",
            "target_unit": "hours",
            "rul_cap_hours": RUL_CAP_HOURS,
            "metrics": rul_metrics,
            "estimator": make_regressor(data.known.copy()),
            "fold_models": folds,
        },
    )
    return {"profile": profile, "source_dataset": data.source_dataset, "failure": failure_metrics, "rul": rul_metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", nargs="*", choices=sorted(LOADERS), help="Profiles to train (default: all).")
    args = parser.parse_args()
    profiles = args.profile or list(LOADERS)
    print(json.dumps({profile: train_profile(profile) for profile in profiles}, indent=2))


if __name__ == "__main__":
    main()
