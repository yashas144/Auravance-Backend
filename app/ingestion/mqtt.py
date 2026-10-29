"""MQTT subscriber that forwards telemetry into the REST ingest service."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from fastapi import HTTPException

from app.core.config import settings
from app.ingestion.mqtt_broker import EmbeddedMqttBroker
from app.ingestion.mqtt_protocol import decode_telemetry_message
from app.models.schemas import MqttIngestStatusResponse

logger = logging.getLogger(__name__)


@dataclass
class MqttRuntime:
    enabled: bool = False
    connected: bool = False
    embedded_broker: bool = False
    broker_host: str = "127.0.0.1"
    broker_port: int = 1883
    topic: str = ""
    messages_accepted: int = 0
    messages_rejected: int = 0
    detail: str = "MQTT ingest is disabled."
    broker: EmbeddedMqttBroker | None = None
    client: object | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


_runtime = MqttRuntime()


def mqtt_status() -> MqttIngestStatusResponse:
    with _runtime.lock:
        return MqttIngestStatusResponse(
            enabled=_runtime.enabled,
            connected=_runtime.connected,
            embedded_broker=_runtime.embedded_broker,
            broker_host=_runtime.broker_host,
            broker_port=_runtime.broker_port,
            topic=_runtime.topic or settings.mqtt_topic,
            messages_accepted=_runtime.messages_accepted,
            messages_rejected=_runtime.messages_rejected,
            detail=_runtime.detail,
        )


def handle_mqtt_message(topic: str, payload: bytes | str | dict) -> None:
    from app.services.telemetry import telemetry_service

    reading = decode_telemetry_message(topic, payload)
    telemetry_service.ingest(reading)


def _on_connect(client, userdata, flags, reason_code, properties=None) -> None:
    ok = int(getattr(reason_code, "value", reason_code) or 0) == 0
    with _runtime.lock:
        _runtime.connected = ok
        _runtime.detail = "MQTT subscriber connected." if ok else f"MQTT connect failed: {reason_code}"
    if ok:
        client.subscribe(settings.mqtt_topic)


def _on_disconnect(client, userdata, flags, reason_code, properties=None) -> None:
    with _runtime.lock:
        _runtime.connected = False
        if _runtime.enabled:
            _runtime.detail = f"MQTT subscriber disconnected: {reason_code}"


def _on_message(client, userdata, message) -> None:
    try:
        handle_mqtt_message(message.topic, message.payload)
        with _runtime.lock:
            _runtime.messages_accepted += 1
    except (HTTPException, ValueError) as exc:
        logger.warning("Rejected MQTT telemetry on %s: %s", getattr(message, "topic", ""), exc)
        with _runtime.lock:
            _runtime.messages_rejected += 1
    except Exception:
        logger.exception("MQTT telemetry handler failed.")
        with _runtime.lock:
            _runtime.messages_rejected += 1


def start_mqtt() -> MqttRuntime:
    with _runtime.lock:
        _runtime.enabled = bool(settings.mqtt_enabled)
        _runtime.broker_host = settings.mqtt_broker_host
        _runtime.broker_port = settings.mqtt_broker_port
        _runtime.topic = settings.mqtt_topic
        _runtime.messages_accepted = 0
        _runtime.messages_rejected = 0
        if not settings.mqtt_enabled:
            _runtime.detail = "MQTT ingest is disabled."
            return _runtime

    try:
        if settings.mqtt_embedded:
            broker = EmbeddedMqttBroker(settings.mqtt_broker_host, settings.mqtt_broker_port)
            broker.start()
            with _runtime.lock:
                _runtime.broker = broker
                _runtime.embedded_broker = True
                _runtime.broker_port = broker.bound_port
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            protocol=mqtt.MQTTv311,
        )
        username = settings.mqtt_username or ("ingest" if settings.ingest_api_key else "")
        password = settings.mqtt_password or settings.ingest_api_key
        if username:
            client.username_pw_set(username, password or None)
        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect
        client.on_message = _on_message
        last_error: Exception | None = None
        attempts = 20 if settings.mqtt_embedded else 50
        delay = 0.05 if settings.mqtt_embedded else 0.1
        for _ in range(attempts):
            try:
                client.connect(_runtime.broker_host, _runtime.broker_port, keepalive=30)
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                time.sleep(delay)
        if last_error is not None:
            raise last_error
        client.loop_start()
        with _runtime.lock:
            _runtime.client = client
            _runtime.enabled = True
            _runtime.detail = "MQTT subscriber starting."
    except Exception as exc:
        logger.warning("MQTT ingest did not start; REST ingest is still available. %s", exc)
        stop_mqtt()
        with _runtime.lock:
            _runtime.enabled = True
            _runtime.connected = False
            _runtime.detail = f"MQTT ingest unavailable: {exc}"
    return _runtime


def stop_mqtt() -> None:
    with _runtime.lock:
        client = _runtime.client
        broker = _runtime.broker
        _runtime.client = None
        _runtime.broker = None
        _runtime.connected = False
        _runtime.embedded_broker = False
    if client is not None:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
    if broker is not None:
        broker.stop()
