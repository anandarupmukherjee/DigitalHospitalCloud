from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.utils import timezone

from tracker.models import TrayStatus
from .telegram import send_message

logger = logging.getLogger(__name__)


def _build_message(tray: TrayStatus) -> str:
    location = tray.location_label or "Unknown location"
    status_time = tray.activated_at or tray.updated_at
    timestamp = status_time.strftime("%Y-%m-%d %H:%M UTC") if status_time else "unknown"
    return (
        f"*Active Tray Alert*\n"
        f"Tray: `{tray.tray_id}`\n"
        f"Location: {location}\n"
        f"Topic: `{tray.topic or 'n/a'}`\n"
        f"Last activity: {timestamp}"
    )


def _due_trays(trays: Iterable[TrayStatus], now):
    """Yield trays whose alert window has elapsed."""
    interval_minutes = getattr(settings, "TRAY_ALERT_INTERVAL_MINUTES", 30)
    alert_delta = timedelta(minutes=interval_minutes)
    for tray in trays:
        last_sent = tray.last_alert_sent_at
        if last_sent and now - last_sent < alert_delta:
            continue
        yield tray


def notify_active_trays() -> int:
    """
    Send Telegram alerts for trays that are currently active.

    Returns the number of trays that triggered a notification.
    """
    if not (getattr(settings, "TELEGRAM_BOT_TOKEN", "") and getattr(settings, "TELEGRAM_CHAT_ID", "")):
        logger.info("Telegram not configured; skipping active tray alert check.")
        return 0

    now = timezone.now()
    active_trays = TrayStatus.objects.filter(is_active=True).order_by("tray_id")
    sent_count = 0

    for tray in _due_trays(active_trays, now):
        message = _build_message(tray)
        if send_message(message):
            tray.last_alert_sent_at = now
            tray.save(update_fields=["last_alert_sent_at"])
            sent_count += 1

    return sent_count
