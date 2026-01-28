from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from tracker.models import (
    TrayEvent,
    TrayHeartbeat,
    TrayHeartbeatEvent,
    TrayStatus,
)

logger = logging.getLogger(__name__)

HEARTBEAT_GRACE_SECONDS = getattr(settings, "TRAY_HEARTBEAT_STALE_SECONDS", 5)


def record_tray_state(
    tray_id: str,
    *,
    topic: str | None = "",
    location_label: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    is_active: bool,
    payload: Optional[Dict[str, Any]] = None,
    event_time=None,
) -> TrayStatus:
    """Store or update the latest snapshot for a tray tracker."""
    if not tray_id:
        raise ValueError("tray_id is required")

    payload = payload or {}
    event_time = event_time or timezone.now()

    normalized_topic = topic or ""

    tray, _ = TrayStatus.objects.get_or_create(
        tray_id=tray_id,
        topic=normalized_topic,
        defaults={
            "location_label": location_label,
            "latitude": latitude,
            "longitude": longitude,
            "is_active": is_active,
            "activated_at": event_time if is_active else None,
            "deactivated_at": None if is_active else event_time,
            "last_alert_sent_at": None,
            "last_payload": payload,
        },
    )

    tray.topic = normalized_topic
    tray.location_label = location_label or tray.location_label
    tray.latitude = latitude if latitude is not None else tray.latitude
    tray.longitude = longitude if longitude is not None else tray.longitude
    tray.is_active = is_active
    if is_active:
        tray.activated_at = event_time
    else:
        tray.deactivated_at = event_time
        tray.last_alert_sent_at = None
    tray.last_payload = payload
    tray.save(update_fields=[
        "topic",
        "location_label",
        "latitude",
        "longitude",
        "is_active",
        "activated_at",
        "deactivated_at",
        "last_alert_sent_at",
        "last_payload",
        "updated_at",
    ])

    TrayEvent.objects.create(
        tray=tray,
        status=TrayEvent.STATUS_ON if is_active else TrayEvent.STATUS_OFF,
        timestamp=event_time,
        topic=normalized_topic,
        payload=payload,
    )

    logger.debug("Tray %s updated (%s)", tray_id, "active" if is_active else "inactive")
    return tray


def record_tray_heartbeat(
    tray_id: str,
    *,
    topic: str | None = "",
    payload: Optional[Dict[str, Any]] = None,
    event_time=None,
) -> TrayHeartbeat:
    """Persist heartbeat information for a tray."""
    if not tray_id:
        raise ValueError("tray_id is required for heartbeat tracking")

    event_time = event_time or timezone.now()
    payload = payload or {}
    normalized_topic = topic or ""

    heartbeat, created = TrayHeartbeat.objects.get_or_create(
        tray_id=tray_id,
        topic=normalized_topic,
        defaults={"last_seen_at": event_time, "last_payload": payload},
    )
    last_seen = heartbeat.last_seen_at
    heartbeat.last_seen_at = event_time
    heartbeat.last_payload = payload
    heartbeat.save(update_fields=["last_seen_at", "last_payload", "updated_at"])

    gap_seconds = None
    if last_seen:
        gap_seconds = (event_time - last_seen).total_seconds()

    events_to_create = []
    if (
        last_seen
        and gap_seconds is not None
        and gap_seconds > HEARTBEAT_GRACE_SECONDS
    ):
        down_timestamp = last_seen + timedelta(seconds=HEARTBEAT_GRACE_SECONDS)
        note = f"No heartbeat for {int(gap_seconds)}s"
        events_to_create.append(
            TrayHeartbeatEvent(
                heartbeat=heartbeat,
                status=TrayHeartbeatEvent.STATUS_DOWN,
                timestamp=down_timestamp,
                note=note,
                payload=payload,
            )
        )

    alive_note = "Initial heartbeat" if created or not last_seen else ""
    if gap_seconds and gap_seconds > HEARTBEAT_GRACE_SECONDS:
        alive_note = f"Heartbeat restored after {int(gap_seconds)}s gap"
    events_to_create.append(
        TrayHeartbeatEvent(
            heartbeat=heartbeat,
            status=TrayHeartbeatEvent.STATUS_ALIVE,
            timestamp=event_time,
            note=alive_note,
            payload=payload,
        )
    )
    TrayHeartbeatEvent.objects.bulk_create(events_to_create)
    logger.debug("Heartbeat recorded for %s (%ss gap)", tray_id, gap_seconds or 0)
    return heartbeat
