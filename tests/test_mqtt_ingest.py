from __future__ import annotations

import json
import socket
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.ingestion.mqtt_protocol import build_telemetry_topic, decode_telemetry_message, parse_telemetry_topic
from app.main import app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class MqttProtocolTests(unittest.TestCase):
    def test_topic_round_trip(self) -> None:
        topic = build_telemetry_topic("plant-a", "line-1", "pump-04")
        self.assertEqual(topic, "plants/plant-a/lines/line-1/assets/pump-04/telemetry")
        self.assertEqual(parse_telemetry_topic(topic), ("plant-a", "line-1", "pump-04"))
        self.assertIsNone(parse_telemetry_topic("plants/plant-a/pump-04"))

    def test_payload_uses_topic_asset_id(self) -> None:
        topic = build_telemetry_topic("plant-b", "line-2", "pump-04")
        reading = decode_telemetry_message(
            topic,
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "asset_id": "someone-else",
                "metrics": {"temperature_c": 70.0, "vibration_rms": 0.3, "pressure_bar": 5.0, "current_a": 9.0},
                "source_context": {"dataset": "kaggle-pump-sensor"},
            },
        )
        self.assertEqual(reading.asset_id, "pump-04")
        self.assertEqual(reading.source, "mqtt")
        self.assertEqual(reading.source_context["plant_id"], "plant-b")
        self.assertEqual(reading.source_context["payload_asset_id"], "someone-else")


class MqttIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._original = (
            settings.demo_db_path,
            settings.database_url,
            settings.redis_url,
            settings.ingest_api_key,
            settings.mqtt_enabled,
            settings.mqtt_embedded,
            settings.mqtt_broker_host,
            settings.mqtt_broker_port,
        )
        settings.demo_db_path = str(Path(self._tmp.name) / "test.db")
        settings.database_url = ""
        settings.redis_url = ""
        settings.ingest_api_key = ""
        settings.mqtt_enabled = True
        settings.mqtt_embedded = True
        settings.mqtt_broker_host = "127.0.0.1"
        settings.mqtt_broker_port = _free_port()

    def tearDown(self) -> None:
        (
            settings.demo_db_path,
            settings.database_url,
            settings.redis_url,
            settings.ingest_api_key,
            settings.mqtt_enabled,
            settings.mqtt_embedded,
            settings.mqtt_broker_host,
            settings.mqtt_broker_port,
        ) = self._original
        self._tmp.cleanup()

    def test_mqtt_publish_reaches_telemetry_store(self) -> None:
        import paho.mqtt.client as mqtt

        with TestClient(app) as client:
            status = client.get("/api/v1/telemetry/ingest/status").json()
            self.assertTrue(status["enabled"], status)
            self.assertTrue(status["embedded_broker"], status)
            publisher = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test-publisher", protocol=mqtt.MQTTv311)
            publisher.connect(status["broker_host"], status["broker_port"], keepalive=10)
            publisher.loop_start()
            topic = build_telemetry_topic("plant-b", "line-1", "pump-04")
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "asset_id": "pump-04",
                "metrics": {"temperature_c": 71.5, "vibration_rms": 0.33, "pressure_bar": 5.1, "current_a": 9.2},
                "source_context": {"dataset": "kaggle-pump-sensor", "machine_status": "NORMAL"},
            }
            publisher.publish(topic, json.dumps(payload), qos=0)
            headers = {
                "Authorization": "Bearer "
                + client.post(
                    "/api/v1/auth/login",
                    json={"email": "yashas@auravance.demo", "password": "Auravance@123"},
                ).json()["access_token"]
            }
            latest = None
            for _ in range(20):
                time.sleep(0.1)
                response = client.get("/api/v1/telemetry/assets/pump-04/latest", headers=headers)
                if response.status_code == 200:
                    latest = response.json()
                    break
            publisher.loop_stop()
            publisher.disconnect()
            self.assertIsNotNone(latest, "MQTT reading was not ingested")
            self.assertEqual(latest["source"], "mqtt")
            self.assertEqual(latest["temperature_c"], 71.5)
            self.assertEqual(latest["source_context"]["machine_status"], "NORMAL")


if __name__ == "__main__":
    unittest.main()
