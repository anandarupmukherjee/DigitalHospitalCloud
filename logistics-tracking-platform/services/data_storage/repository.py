from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.utils import timezone

from tracker.models import TrayEvent, TrayStatus

logger = logging.getLogger(__name__)


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
    tray.last_payload = payload
    tray.save(update_fields=[
        "topic",
        "location_label",
        "latitude",
        "longitude",
        "is_active",
        "activated_at",
        "deactivated_at",
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
