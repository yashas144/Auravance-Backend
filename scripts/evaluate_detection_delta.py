"""Measure rules-vs-model failure detection on the local replay datasets.

Defines detection as ranking currently-failed (or leaking) rows above healthy
rows. Records the relative ROC-AUC gain versus the rules scorer. Does not claim
a 30% improvement unless the measured delta reaches that.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.replay import DATASETS, build_payload, downsample, group_episodes, read_replay_rows  # noqa: E402
from app.models.schemas import TelemetryRecord  # noqa: E402
from app.services.model_registry import models_for  # noqa: E402
from app.services.scoring import rules_anomaly_and_failure  # noqa: E402


DOWN_STATUSES = {"BROKEN", "RECOVERING", "AIR_LEAK", "FAILED"}
OUTPUT = BACKEND_DIR / "artifacts" / "models" / "detection_delta.json"


def replay_records(profile: str) -> list[tuple[int, list[TelemetryRecord]]]:
    dataset = DATASETS[profile]
    mappings = dataset.load_mappings()
    samples: list[tuple[int, list[TelemetryRecord]]] = []
    for episode in group_episodes(read_replay_rows(dataset.replay_path)):
        history: list[TelemetryRecord] = []
        for row in downsample(episode, stride=5):
            payload = build_payload(row, f"{profile}-eval", "", mappings, dataset)
            history.append(
                TelemetryRecord(
                    asset_id=f"{profile}-eval",
                    timestamp=datetime.now(timezone.utc),
                    source_context=payload["source_context"],
                    **payload["metrics"],
                )
            )
            history = history[-12:]
            samples.append((1 if row.machine_status in DOWN_STATUSES else 0, list(history)))
    return samples


def auc(labels: list[int], scores: list[float]) -> float | None:
    array_labels = np.asarray(labels)
    array_scores = np.asarray(scores, dtype=np.float64)
    if len(np.unique(array_labels)) < 2:
        return None
    return round(float(roc_auc_score(array_labels, array_scores)), 4)


def relative_gain(baseline: float | None, model: float | None) -> float | None:
    if baseline is None or model is None or baseline <= 0:
        return None
    return round(100.0 * (model - baseline) / baseline, 2)


def evaluate_profile(profile: str) -> dict[str, object]:
    models = models_for(profile)
    labels: list[int] = []
    rules_scores: list[float] = []
    anomaly_scores: list[float] = []
    tabular_scores: list[float] = []
    sequence_scores: list[float] = []
    sequence_labels: list[int] = []
    for label, history in replay_records(profile):
        labels.append(label)
        _rules_anomaly, rules_failure = rules_anomaly_and_failure(history)
        rules_scores.append(rules_failure)
        anomaly = models.anomaly.predict(history)
        anomaly_scores.append(anomaly.score if anomaly else rules_failure)
        tabular = models.failure.predict(history)
        tabular_scores.append(tabular.probability if tabular else rules_failure)
        sequence = models.sequence.predict(history)
        if sequence is not None:
            sequence_scores.append(sequence.probability)
            sequence_labels.append(label)

    rules_auc = auc(labels, rules_scores)
    tabular_auc = auc(labels, tabular_scores)
    result = {
        "profile": profile,
        "rows": len(labels),
        "positive_rate": round(float(np.mean(labels)), 4) if labels else 0.0,
        "rules_roc_auc": rules_auc,
        "isolation_forest_roc_auc": auc(labels, anomaly_scores),
        "tabular_algorithm": models.failure.status().algorithm,
        "tabular_roc_auc": tabular_auc,
        "tabular_vs_rules_pct": relative_gain(rules_auc, tabular_auc),
        "lstm_loaded": models.sequence.status().loaded,
        "lstm_rows": len(sequence_scores),
        "lstm_roc_auc": auc(sequence_labels, sequence_scores) if sequence_scores else None,
    }
    result["lstm_vs_rules_pct"] = relative_gain(rules_auc, result["lstm_roc_auc"] if isinstance(result["lstm_roc_auc"], float) else None)
    result["meets_30pct_north_star"] = bool(
        (result["tabular_vs_rules_pct"] or 0) >= 30 or (result["lstm_vs_rules_pct"] or 0) >= 30
    )
    return result


def main() -> None:
    profiles = {profile: evaluate_profile(profile) for profile in DATASETS}
    payload = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "definition": "ROC-AUC for ranking currently-failed replay rows above healthy rows",
        "baseline": "rules scorer in app.services.scoring.rules_anomaly_and_failure",
        "note": "The north-star 30% claim is recorded only when meets_30pct_north_star is true.",
        "profiles": profiles,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
