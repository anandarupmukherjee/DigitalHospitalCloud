from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

import paho.mqtt.client as mqtt

from services.data_storage.repository import record_tray_heartbeat, record_tray_state

logger = logging.getLogger(__name__)


class TrayMQTTListener:
    """MQTT listener that consumes tray tracker events and persists them."""

    def __init__(
        self,
        *,
        broker_host: str | None = None,
        broker_port: int | None = None,
        topic: str | None = None,
        status_topic: str | None = None,
        keepalive: int = 60,
    ) -> None:
        self.broker_host = broker_host or os.environ.get("MQTT_BROKER_HOST", "broker.hivemq.com")
        self.broker_port = broker_port or int(os.environ.get("MQTT_BROKER_PORT", "1883"))
        self.topic = topic or os.environ.get("MQTT_TOPIC", "MET/hospital/sensors/#")
        self.status_topic = status_topic or os.environ.get("MQTT_STATUS_TOPIC", "MET/hospital/status/#")
        self.status_topic_base = None
        if self.status_topic:
            base = self.status_topic.split("#", 1)[0]
            base = base.split("+", 1)[0]
            self.status_topic_base = base.rstrip("/")
        self.keepalive = keepalive

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def start(self) -> None:
        logger.info("Connecting to MQTT broker %s:%s", self.broker_host, self.broker_port)
        self.client.connect(self.broker_host, self.broker_port, self.keepalive)
        self.client.loop_forever()

    # MQTT callbacks -----------------------------------------------------
    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        logger.info(
            "Connected to MQTT broker with result %s. Subscribing to %s + %s",
            reason_code,
            self.topic,
            self.status_topic,
        )
        client.subscribe(self.topic)
        if self.status_topic:
            client.subscribe(self.status_topic)

    def on_message(self, client, userdata, message):
        payload = self._deserialize_payload(message.payload)
        topic = message.topic or ""
        if self.status_topic and mqtt.topic_matches_sub(self.status_topic, topic):
            self._handle_heartbeat(topic, payload)
            return
        self._handle_tray_status(topic, payload)

    # Message handlers --------------------------------------------------
    def _handle_tray_status(self, topic: str, payload: Dict[str, Any]) -> None:
        tray_id = payload.get("tray_id") or self._tray_id_from_topic(topic)
        if not tray_id:
            logger.warning("Received message without tray_id: %s", payload)
            return

        location = payload.get("location") or {}
        latitude = payload.get("latitude", location.get("latitude") or location.get("lat"))
        longitude = payload.get("longitude", location.get("longitude") or location.get("lon"))
        location_label = (
            payload.get("location_label")
            or location.get("label")
            or location.get("name")
            or ""
        )
        status_value = (payload.get("status") or "").lower()
        if status_value not in {"on", "off"}:
            logger.debug("Ignoring non-status message on %s: %s", topic, payload)
            return
        is_active = status_value == "on"

        record_tray_state(
            tray_id,
            topic=topic,
            location_label=location_label,
            latitude=_safe_float(latitude),
            longitude=_safe_float(longitude),
            is_active=is_active,
            payload=payload,
        )

    def _handle_heartbeat(self, topic: str, payload: Dict[str, Any]) -> None:
        tray_id = (
            payload.get("tray_id")
            or self._tray_id_from_status_topic(topic)
            or self._tray_id_from_topic(topic)
        )
        if not tray_id:
            logger.debug("Heartbeat without tray_id ignored (topic=%s payload=%s)", topic, payload)
            return
        record_tray_heartbeat(
            tray_id,
            topic=topic,
            payload=payload,
        )

    # Helpers ------------------------------------------------------------
    def _deserialize_payload(self, payload: bytes) -> Dict[str, Any]:
        text = payload.decode("utf-8", errors="ignore").strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            parts = text.split(",")
            result = {}
            for part in parts:
                if "=" in part:
                    key, value = part.split("=", 1)
                    result[key.strip()] = value.strip()
            if "tray_id" not in result and parts:
                result["tray_id"] = parts[0].strip()
            return result

    def _tray_id_from_topic(self, topic: str | None) -> str | None:
        if not topic:
            return None
        cleaned = topic.strip("/")
        if not cleaned:
            return None
        segments = [segment for segment in cleaned.split("/") if segment]
        return segments[-1] if segments else None

    def _tray_id_from_status_topic(self, topic: str | None) -> str | None:
        if not topic or not self.status_topic_base:
            return None
        base = self.status_topic_base
        if base and topic.startswith(f"{base}/"):
            remainder = topic[len(base) + 1 :]
            if not remainder:
                return None
            return remainder.split("/", 1)[0]
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
