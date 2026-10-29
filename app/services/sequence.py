"""LSTM sequence failure scoring, loaded beside tabular models.

Torch is imported only when an artifact is served. Tabular XGBoost/HGB remains
the fallback when the window is short, torch is missing, or the artifact fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from app.core.config import settings
from app.models.schemas import AnomalyModelStatusResponse, TelemetryRecord
from app.services.anomaly import RUNTIME_PROFILE, valid_feature_names
from app.services.prognostics import runtime_features


@dataclass(slots=True)
class SequenceInference:
    probability: float
    model_version: str


def numpy_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value.detach().cpu().numpy() if hasattr(value, "detach") else value for key, value in state.items()}


def build_lstm(n_features: int, hidden_size: int, num_layers: int):
    import torch
    from torch import nn

    class FailureLSTM(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lstm = nn.LSTM(n_features, hidden_size, num_layers, batch_first=True)
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, sequence):
            output, _ = self.lstm(sequence)
            logits = self.head(output[:, -1, :])
            return torch.sigmoid(logits).squeeze(-1)

    return FailureLSTM()


def load_lstm_from_state(artifact: dict[str, Any], state: dict[str, Any]):
    import torch

    model = build_lstm(len(artifact["feature_names"]), int(artifact["hidden_size"]), int(artifact["num_layers"]))
    tensors = {key: torch.from_numpy(value) if hasattr(value, "shape") else value for key, value in state.items()}
    model.load_state_dict(tensors)
    model.eval()
    return model


def window_features(telemetry: list[TelemetryRecord], artifact: dict[str, Any]) -> list[list[float]] | None:
    window_size = int(artifact.get("window_size") or settings.sequence_window_size)
    if len(telemetry) < window_size:
        return None
    profile = artifact.get("runtime_profile", RUNTIME_PROFILE)
    names = artifact["feature_names"]
    return [runtime_features(record, profile, names) for record in telemetry[-window_size:]]


class SequenceFailureService:
    def __init__(self, artifact_path: Path | str | None = None) -> None:
        self._path = Path(artifact_path) if artifact_path is not None else None
        self._artifact: dict[str, Any] | None = None
        self._models: dict[str, Any] = {}
        self._load_error: str | None = None
        self._loaded_path: Path | None = None
        self._lock = Lock()

    @property
    def artifact_path(self) -> Path:
        return self._path or Path(settings.model_registry_path) / "failure_lstm.joblib"

    def _load(self) -> dict[str, Any] | None:
        path = self.artifact_path
        if self._loaded_path == path and (self._artifact is not None or self._load_error is not None):
            return self._artifact
        with self._lock:
            if self._loaded_path == path and (self._artifact is not None or self._load_error is not None):
                return self._artifact
            self._loaded_path = path
            self._artifact = None
            self._models = {}
            self._load_error = None
            if not path.exists():
                self._load_error = f"Sequence artifact not found: {path.name}"
                return None
            try:
                import torch  # noqa: F401
                import joblib

                artifact = joblib.load(path)
                if artifact.get("artifact_schema_version") != 1:
                    raise ValueError("Unsupported sequence artifact schema.")
                if artifact.get("task") != "failure_sequence":
                    raise ValueError("Sequence artifact task does not match failure_sequence.")
                if not valid_feature_names(artifact.get("feature_names")):
                    raise ValueError("Sequence feature contract does not match live telemetry.")
                self._artifact = artifact
            except ModuleNotFoundError:
                self._load_error = "PyTorch is not installed. pip install -e '.[sequence]' to serve LSTM models."
            except Exception as exc:
                self._load_error = f"Unable to load sequence artifact: {exc}"
            return self._artifact

    def _estimator_for(self, artifact: dict[str, Any], latest: TelemetryRecord):
        version = str(artifact["model_version"])
        state = artifact["state_dict"]
        key = "full"
        context = latest.source_context
        recorded_at = context.get("source_timestamp")
        if context.get("dataset") == artifact.get("fold_dataset") and isinstance(recorded_at, str):
            for index, fold in enumerate(artifact.get("fold_models", [])):
                if fold["held_out_start"] <= recorded_at <= fold["held_out_end"]:
                    state = fold["state_dict"]
                    version = f"{version}+heldout-{index}"
                    key = f"fold-{index}"
                    break
        if key not in self._models:
            self._models[key] = load_lstm_from_state(artifact, state)
        return self._models[key], version

    def predict(self, telemetry: list[TelemetryRecord]) -> SequenceInference | None:
        artifact = self._load()
        if artifact is None:
            return None
        window = window_features(telemetry, artifact)
        if window is None:
            return None
        import torch

        model, model_version = self._estimator_for(artifact, telemetry[-1])
        with torch.no_grad():
            tensor = torch.tensor([window], dtype=torch.float32)
            probability = float(model(tensor).item())
        return SequenceInference(
            probability=round(min(0.99, max(0.01, probability)), 4),
            model_version=model_version,
        )

    def status(self) -> AnomalyModelStatusResponse:
        artifact = self._load()
        if artifact is None:
            return AnomalyModelStatusResponse(
                loaded=False,
                artifact_exists=self.artifact_path.exists(),
                model_version="tabular-fallback",
                algorithm="lstm-unavailable",
                fallback_active=True,
                detail=self._load_error or "Sequence model is unavailable.",
            )
        return AnomalyModelStatusResponse(
            loaded=True,
            artifact_exists=True,
            model_version=str(artifact["model_version"]),
            algorithm=str(artifact["algorithm"]),
            trained_at=artifact.get("trained_at"),
            source_dataset=artifact.get("source_dataset"),
            feature_names=list(artifact["feature_names"]),
            metrics={key: float(value) for key, value in artifact.get("metrics", {}).items()},
            fallback_active=False,
            detail="LSTM sequence model loaded and serving when history is long enough.",
        )


sequence_failure_service = SequenceFailureService()
