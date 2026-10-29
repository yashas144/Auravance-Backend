"""MQTT topic parsing and telemetry payload normalization.

MQTT is an additional producer into `telemetry_service`. The public ingest
contract is the same as REST: four sensor channels plus optional source_context.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from app.models.schemas import TelemetryIngestRequest, TelemetryMetrics


MQTT_TOPIC_TEMPLATE = "plants/{plant_id}/lines/{line_id}/assets/{asset_id}/telemetry"
MQTT_SOURCE = "mqtt"


def parse_telemetry_topic(topic: str) -> tuple[str, str, str] | None:
    parts = [part for part in topic.split("/") if part]
    if len(parts) != 7:
        return None
    if parts[0] != "plants" or parts[2] != "lines" or parts[4] != "assets" or parts[6] != "telemetry":
        return None
    return parts[1], parts[3], parts[5]


def build_telemetry_topic(plant_id: str, line_id: str, asset_id: str) -> str:
    return MQTT_TOPIC_TEMPLATE.format(plant_id=plant_id, line_id=line_id, asset_id=asset_id)


def decode_telemetry_message(topic: str, payload: bytes | str | dict) -> TelemetryIngestRequest:
    parsed = parse_telemetry_topic(topic)
    if parsed is None:
        raise ValueError(f"Unsupported MQTT topic: {topic}")
    plant_id, line_id, asset_id = parsed

    if isinstance(payload, dict):
        body = payload
    else:
        raw = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("MQTT payload is not JSON.") from exc
    if not isinstance(body, dict):
        raise ValueError("MQTT payload must be a JSON object.")

    metrics_raw = body.get("metrics", body)
    try:
        metrics = TelemetryMetrics.model_validate(metrics_raw)
    except ValidationError as exc:
        raise ValueError("MQTT payload does not match the telemetry contract.") from exc

    context = dict(body.get("source_context") or {})
    context.setdefault("plant_id", plant_id)
    context.setdefault("line_id", line_id)
    context.setdefault("mqtt_topic", topic)
    if body.get("asset_id") and body["asset_id"] != asset_id:
        context["payload_asset_id"] = body["asset_id"]

    timestamp = body.get("timestamp") or datetime.now(timezone.utc)
    return TelemetryIngestRequest(
        timestamp=timestamp,
        asset_id=asset_id,
        metrics=metrics,
        source=str(body.get("source") or MQTT_SOURCE),
        source_context=context,
    )
