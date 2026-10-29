from __future__ import annotations

from typing import NamedTuple

from app.services.anomaly import AnomalyModelService, anomaly_model_service
from app.services.model_profiles import DEFAULT_PROFILE, PROFILES, artifact_paths
from app.services.prognostics import FailureModelService, RulModelService
from app.services.sequence import SequenceFailureService


class ProfileModels(NamedTuple):
    anomaly: AnomalyModelService
    failure: FailureModelService
    rul: RulModelService
    sequence: SequenceFailureService


def _build() -> dict[str, ProfileModels]:
    pump_paths = artifact_paths("pump")
    models = {
        "pump": ProfileModels(
            anomaly_model_service,
            FailureModelService(pump_paths["failure"]),
            RulModelService(pump_paths["rul"]),
            SequenceFailureService(pump_paths["sequence"]),
        )
    }
    for profile in PROFILES:
        if profile in models:
            continue
        paths = artifact_paths(profile)
        models[profile] = ProfileModels(
            AnomalyModelService(paths["anomaly"]),
            FailureModelService(paths["failure"]),
            RulModelService(paths["rul"]),
            SequenceFailureService(paths["sequence"]),
        )
    return models


MODELS = _build()


def models_for(profile: str) -> ProfileModels:
    return MODELS.get(profile, MODELS[DEFAULT_PROFILE])
