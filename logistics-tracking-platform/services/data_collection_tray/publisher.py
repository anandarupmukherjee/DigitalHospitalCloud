from __future__ import annotations

import json
import os
from typing import Any, Dict

import paho.mqtt.client as mqtt


class TrayConfigPublisher:
    """Publishes configuration messages to tray Pico devices."""

    def __init__(
        self,
        *,
        broker_host: str | None = None,
        broker_port: int | None = None,
        config_topic: str | None = None,
        legacy_topic_template: str | None = None,
        keepalive: int = 60,
    ) -> None:
        self.broker_host = broker_host or os.environ.get("MQTT_BROKER_HOST", "broker.hivemq.com")
        self.broker_port = broker_port or int(os.environ.get("MQTT_BROKER_PORT", "1883"))
        self.config_topic = config_topic
        if self.config_topic is None:
            self.config_topic = os.environ.get("MQTT_CONFIG_TOPIC", "MET/hospital/sensors/configure")
        legacy_env = os.environ.get("MQTT_LEGACY_CONFIG_TOPIC", "tray/{pico_id}/config")
        if legacy_env == "":
            legacy_env = None
        self.legacy_topic_template = legacy_topic_template if legacy_topic_template is not None else legacy_env
        self.keepalive = keepalive

    def available_topic_templates(self) -> list[str]:
        templates: list[str] = []
        for topic in (self.config_topic, self.legacy_topic_template):
            if topic and topic not in templates:
                templates.append(topic)
        return templates

    def resolve_topics(self, pico_id: str) -> list[str]:
        resolved: list[str] = []
        for template in self.available_topic_templates():
            if "{pico_id}" in template:
                resolved.append(template.format(pico_id=pico_id))
            else:
                resolved.append(template)
        return resolved

    def publish(self, payload: Dict[str, Any]) -> None:
        pico_id = payload.get("pico_id")
        if not pico_id:
            raise ValueError("payload must include pico_id")

        topics = self.resolve_topics(pico_id)
        if not topics:
            raise ValueError("No configuration topics available to publish to.")

        client = mqtt.Client()
        client.connect(self.broker_host, self.broker_port, self.keepalive)
        try:
            message = json.dumps(payload)
            for topic in topics:
                # retain so dormant Picos replay the latest config when they reconnect
                info = client.publish(topic, message, qos=1, retain=True)
                info.wait_for_publish()
                client.loop(timeout=0.1)
        finally:
            client.disconnect()
