"""Which trained model set (profile) scores which kind of asset.

Each profile is trained on a real dataset recorded from that kind of machine:
  pump       - Kaggle pump-sensor recording (7 breakdowns)
  compressor - MetroPT-3 metro air compressor (4 air leaks)
  motor      - NASA/IMS motor-driven bearing rig (3 run-to-failure tests)
Drives and conveyors are motor-driven, so they use the motor profile; cooling
skids are pump loops, so they use the pump profile.
"""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

from app.core.config import settings
from app.core.db import DatabaseError, get_connection


DEFAULT_PROFILE = "pump"
PROFILES = ("pump", "compressor", "motor")
PROFILE_DATASETS = {
    "pump": "kaggle-pump-sensor",
    "compressor": "metropt-3",
    "motor": "ims-bearings",
}
ASSET_TYPE_PROFILES = {
    "pump": "pump",
    "cooling-system": "pump",
    "compressor": "compressor",
    "motor": "motor",
    "drive": "motor",
    "conveyor": "motor",
}


def profile_for_asset_type(asset_type: str | None) -> str:
    return ASSET_TYPE_PROFILES.get((asset_type or "").strip().lower(), DEFAULT_PROFILE)


def profile_for_asset(asset_id: str) -> str:
    try:
        with closing(get_connection()) as connection:
            row = connection.execute("SELECT asset_type FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    except DatabaseError:
        return DEFAULT_PROFILE
    return profile_for_asset_type(row["asset_type"] if row else None)


def _usable_tabular(preferred: Path, fallback: Path) -> Path:
    if not preferred.exists():
        return fallback
    sidecar = preferred.with_suffix(".json")
    if not sidecar.exists():
        return preferred
    try:
        metrics = json.loads(sidecar.read_text(encoding="utf-8")).get("metrics", {})
    except (OSError, json.JSONDecodeError):
        return fallback
    if metrics.get("loo_roc_auc") is None and metrics.get("loo_mae_hours") is None:
        return fallback
    return preferred


def artifact_paths(profile: str) -> dict[str, Path]:
    registry = Path(settings.model_registry_path)
    if profile == "pump":
        hgb_failure = Path(settings.failure_model_path)
        hgb_rul = Path(settings.rul_model_path)
        xgb_failure = registry / "failure_xgboost.joblib"
        xgb_rul = registry / "rul_xgboost.joblib"
        sequence = registry / "failure_lstm.joblib"
        anomaly = Path(settings.anomaly_model_path)
    else:
        hgb_failure = registry / f"{profile}_failure_gradient_boosting.joblib"
        hgb_rul = registry / f"{profile}_rul_gradient_boosting.joblib"
        xgb_failure = registry / f"{profile}_failure_xgboost.joblib"
        xgb_rul = registry / f"{profile}_rul_xgboost.joblib"
        sequence = registry / f"{profile}_failure_lstm.joblib"
        anomaly = registry / f"{profile}_anomaly_isolation_forest.joblib"
    return {
        "anomaly": anomaly,
        "failure": _usable_tabular(xgb_failure, hgb_failure),
        "rul": _usable_tabular(xgb_rul, hgb_rul),
        "sequence": sequence,
    }
