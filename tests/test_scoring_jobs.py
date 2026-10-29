from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.scoring_jobs import scoring_offloaded


class ScoringJobsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._original = (settings.demo_db_path, settings.database_url, settings.redis_url, settings.mqtt_enabled)
        settings.demo_db_path = str(Path(self._tmp.name) / "test.db")
        settings.database_url = ""
        settings.redis_url = ""
        settings.mqtt_enabled = False

    def tearDown(self) -> None:
        settings.demo_db_path, settings.database_url, settings.redis_url, settings.mqtt_enabled = self._original
        self._tmp.cleanup()

    def test_empty_redis_url_scores_inline(self) -> None:
        self.assertFalse(scoring_offloaded())
        with TestClient(app) as client:
            health = client.get("/api/v1/health").json()
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["storage"], "sqlite")
            self.assertEqual(health["scoring"], "inline")


if __name__ == "__main__":
    unittest.main()
