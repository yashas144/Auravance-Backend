from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.models.schemas import TelemetryRecord
from app.services.model_registry import models_for
from app.services.sequence import window_features


class SequenceModelTests(unittest.TestCase):
    def test_short_history_does_not_replace_tabular_models(self) -> None:
        models = models_for("pump")
        record = TelemetryRecord(
            asset_id="pump-04",
            timestamp=datetime.now(timezone.utc),
            temperature_c=70.0,
            vibration_rms=0.3,
            pressure_bar=5.0,
            current_a=9.0,
        )
        self.assertIsNone(models.sequence.predict([record]))
        self.assertIsNotNone(models.failure.predict([record]))

    def test_window_builder_requires_configured_length(self) -> None:
        artifact = {
            "window_size": 3,
            "feature_names": ["temperature", "vibration", "pressure", "current"],
            "runtime_profile": {
                "temperature": {"center": 70.0, "scale": 8.0},
                "vibration": {"center": 0.3, "scale": 0.2},
                "pressure": {"center": 5.0, "scale": 0.8},
                "current": {"center": 9.0, "scale": 2.5},
            },
        }
        records = [
            TelemetryRecord(
                asset_id="pump-04",
                timestamp=datetime.now(timezone.utc),
                temperature_c=70.0 + index,
                vibration_rms=0.3,
                pressure_bar=5.0,
                current_a=9.0,
            )
            for index in range(3)
        ]
        window = window_features(records, artifact)
        self.assertIsNotNone(window)
        self.assertEqual(len(window), 3)
        self.assertIsNone(window_features(records[:2], artifact))


if __name__ == "__main__":
    unittest.main()
