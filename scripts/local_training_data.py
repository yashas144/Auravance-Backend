"""Labeled training rows from processed CSVs when present, otherwise replay files."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pump_prognostics_data as pump  # noqa: E402
from app.ingestion.replay import DATASETS, group_episodes, read_replay_rows  # noqa: E402
from app.services.model_profiles import PROFILE_DATASETS, artifact_paths  # noqa: E402


FAILURE_HORIZON_HOURS = 72.0
RUL_CAP_HOURS = 240.0
DOWN_STATUSES = {"BROKEN", "RECOVERING", "AIR_LEAK", "FAILED"}


@dataclass(slots=True)
class LabeledSeries:
    profile: str
    feature_names: list[str]
    features: np.ndarray
    timestamps: np.ndarray
    down: np.ndarray
    hours_to_failure: np.ndarray
    known: np.ndarray
    group: np.ndarray
    failure_times: list[str]
    source_dataset: str
    runtime_profile: dict[str, dict[str, float]]
    fold_dataset: str
    minutes_per_row: float
    forecast_horizon_hours: float = FAILURE_HORIZON_HOURS


def _sidecar(path: Path) -> dict:
    return json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))


def _hours_and_groups(timestamps: np.ndarray, down: np.ndarray, minutes_per_row: float):
    rows = len(down)
    starts = [index for index in range(rows) if down[index] and (index == 0 or not down[index - 1])]
    hours = np.full(rows, np.inf)
    if starts:
        starts_arr = np.asarray(starts, dtype=int)
        next_index = np.searchsorted(starts_arr, np.arange(rows), side="left")
        has_next = next_index < len(starts_arr)
        hours[has_next] = (starts_arr[next_index[has_next]] - np.arange(rows)[has_next]) * (minutes_per_row / 60.0)
    hours[down] = 0.0
    group = np.zeros(rows, dtype=int)
    current = 0
    for index in range(rows):
        if down[index] and (index == 0 or not down[index - 1]):
            current += 1
        group[index] = current
    hours_to_end = (rows - 1 - np.arange(rows)) * (minutes_per_row / 60.0)
    known = (hours < np.inf) | down | (hours_to_end >= FAILURE_HORIZON_HOURS)
    failure_times = [str(timestamps[index]) for index in starts]
    return hours, group, known, failure_times


def load_pump() -> LabeledSeries:
    if pump.DEFAULT_INPUT.exists():
        data = pump.load()
        metadata = _sidecar(artifact_paths("pump")["anomaly"])
        return LabeledSeries(
            profile="pump",
            feature_names=list(data.feature_names),
            features=data.features,
            timestamps=data.timestamps,
            down=data.down,
            hours_to_failure=data.hours_to_failure,
            known=data.failure_label_known,
            group=data.group,
            failure_times=data.failure_times,
            source_dataset=data.source_dataset if hasattr(data, "source_dataset") else "pump_sensor/sensor_processed.csv",
            runtime_profile=data.runtime_profile,
            fold_dataset="kaggle-pump-sensor",
            minutes_per_row=1.0,
            forecast_horizon_hours=FAILURE_HORIZON_HOURS,
        )
    metadata = _sidecar(artifact_paths("pump")["anomaly"])
    columns = metadata["source_columns"]
    medians = metadata["source_transform"]["medians"]
    scales = metadata["source_transform"]["iqr_scales"]
    rows = read_replay_rows(DATASETS["pump"].replay_path)
    features = []
    timestamps = []
    down = []
    groups = []
    for group_index, episode in enumerate(group_episodes(rows)):
        for row in episode:
            values = []
            for column in columns:
                raw = row.raw.get(column)
                center = float(medians[column])
                scale = max(float(scales[column]), 1e-9)
                values.append(0.0 if raw is None else (float(raw) - center) / scale)
            features.append(values)
            timestamps.append(row.source_timestamp)
            down.append(row.machine_status in DOWN_STATUSES)
            groups.append(group_index)
    feature_array = np.asarray(features, dtype=np.float64)
    down_array = np.asarray(down, dtype=bool)
    hours, _group, known, failure_times = _hours_and_groups(np.asarray(timestamps), down_array, 1.0)
    return LabeledSeries(
        profile="pump",
        feature_names=list(metadata["feature_names"]),
        features=feature_array,
        timestamps=np.asarray(timestamps),
        down=down_array,
        hours_to_failure=hours,
        known=known,
        group=np.asarray(groups, dtype=int),
        failure_times=failure_times,
        source_dataset="replay/pump_failure_episodes.csv",
        runtime_profile=metadata["runtime_profile"],
        fold_dataset=PROFILE_DATASETS["pump"],
        minutes_per_row=1.0,
        forecast_horizon_hours=0.0,
    )


def _replay_profile(profile: str, feature_columns: list[str], feature_names: list[str], minutes_per_row: float) -> LabeledSeries:
    metadata = _sidecar(artifact_paths(profile)["failure"])
    runtime_profile = metadata["runtime_profile"]
    rows = read_replay_rows(DATASETS[profile].replay_path)
    values = []
    timestamps = []
    down = []
    groups = []
    for group_index, episode in enumerate(group_episodes(rows)):
        for row in episode:
            sample = []
            for column, name in zip(feature_columns, feature_names, strict=True):
                raw = row.raw.get(column)
                center = float(runtime_profile[name]["center"])
                scale = max(float(runtime_profile[name]["scale"]), 1e-9)
                sample.append(0.0 if raw is None else (float(raw) - center) / scale)
            values.append(sample)
            timestamps.append(row.source_timestamp)
            down.append(row.machine_status in DOWN_STATUSES)
            groups.append(group_index)
    down_array = np.asarray(down, dtype=bool)
    hours, _group, known, failure_times = _hours_and_groups(np.asarray(timestamps), down_array, minutes_per_row)
    source = {
        "compressor": "replay/compressor_failure_episodes.csv",
        "motor": "replay/motor_failure_episodes.csv",
    }[profile]
    processed = {
        "compressor": BACKEND_DIR / "data" / "processed" / "metropt3" / "metropt3_5min.csv",
        "motor": BACKEND_DIR / "data" / "processed" / "ims_bearings" / "ims_features.csv",
    }[profile]
    return LabeledSeries(
        profile=profile,
        feature_names=feature_names,
        features=np.asarray(values, dtype=np.float64),
        timestamps=np.asarray(timestamps),
        down=down_array,
        hours_to_failure=hours,
        known=known,
        group=np.asarray(groups, dtype=int),
        failure_times=failure_times,
        source_dataset=str(processed.relative_to(BACKEND_DIR / "data" / "processed")) if processed.exists() else source,
        runtime_profile=runtime_profile,
        fold_dataset=PROFILE_DATASETS[profile],
        minutes_per_row=minutes_per_row,
        forecast_horizon_hours=0.0 if profile == "compressor" else FAILURE_HORIZON_HOURS,
    )


def load_compressor() -> LabeledSeries:
    return _replay_profile("compressor", ["oil_temperature_c", "tp3_bar", "motor_current_a"], ["temperature", "pressure", "current"], 5.0)


def load_motor() -> LabeledSeries:
    processed = BACKEND_DIR / "data" / "processed" / "ims_bearings" / "ims_features.csv"
    if processed.exists():
        metadata = _sidecar(artifact_paths("motor")["failure"])
        frame = pd.read_csv(processed)
        frame["max_bearing_rms"] = frame.filter(regex=r"bearing_\d_rms").max(axis=1)
        times = pd.to_datetime(frame["source_timestamp"])
        test_end = times.groupby(frame["test_id"]).transform("max")
        hours = ((test_end - times).dt.total_seconds() / 3600).to_numpy()
        down = hours == 0
        runtime_profile = metadata["runtime_profile"]
        center = float(runtime_profile["vibration"]["center"])
        scale = max(float(runtime_profile["vibration"]["scale"]), 1e-9)
        features = ((frame["max_bearing_rms"].to_numpy(dtype=np.float64) - center) / scale).reshape(-1, 1)
        return LabeledSeries(
            profile="motor",
            feature_names=["vibration"],
            features=features,
            timestamps=frame["source_timestamp"].to_numpy(),
            down=down,
            hours_to_failure=hours,
            known=np.ones(len(frame), dtype=bool),
            group=pd.factorize(frame["test_id"])[0],
            failure_times=sorted(frame.loc[down, "source_timestamp"].tolist()),
            source_dataset="ims_bearings/ims_features.csv",
            runtime_profile=runtime_profile,
            fold_dataset="ims-bearings",
            minutes_per_row=10.0,
            forecast_horizon_hours=FAILURE_HORIZON_HOURS,
        )
    return _replay_profile("motor", ["max_bearing_rms"], ["vibration"], 10.0)


LOADERS = {"pump": load_pump, "compressor": load_compressor, "motor": load_motor}
FAILURE_STRATEGY = {"pump": "degradation", "compressor": "sudden", "motor": "degradation"}


def failure_target(data: LabeledSeries) -> np.ndarray:
    if data.forecast_horizon_hours <= 0:
        return data.down.astype(int)
    return (data.down | (data.hours_to_failure < data.forecast_horizon_hours)).astype(int)


def rul_target(data: LabeledSeries) -> np.ndarray:
    rul = np.minimum(data.hours_to_failure, RUL_CAP_HOURS)
    rul[data.down] = 0.0
    return rul


def buckets(data: LabeledSeries) -> dict[str, np.ndarray]:
    up = ~data.down
    hours = data.hours_to_failure
    return {
        "down": data.down,
        "under_24h": up & (hours < 24),
        "24_to_72h": up & (hours >= 24) & (hours < 72),
        "over_72h": up & (hours >= 72),
    }
