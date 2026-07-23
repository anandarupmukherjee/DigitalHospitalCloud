"""Platform/system-health metrics for the System admin dashboard.

Everything here is read-only aggregation over the existing tracker models. It is
intentionally separate from ``analytics.py`` (which is about tray *logistics*
performance) — this module is about the health of the *platform itself*:
ingestion pipeline, database growth, fleet/tray uptime, and support services.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import TrayEvent, TrayHeartbeat, TrayHeartbeatEvent, TrayStatus

# Captured when the worker imports this module — a lower-bound proxy for how long
# this application process has been serving.
PROCESS_START_EPOCH = time.time()


def _container_uptime_seconds():
    """Best-effort uptime of PID 1 (the container), or None if unavailable."""
    try:
        with open("/proc/1/stat") as handle:
            starttime_ticks = float(handle.read().split()[21])
        clk = os.sysconf("SC_CLK_TCK")
        btime = None
        with open("/proc/stat") as handle:
            for line in handle:
                if line.startswith("btime"):
                    btime = int(line.split()[1])
                    break
        if btime is None:
            return None
        start_epoch = btime + starttime_ticks / clk
        return max(0.0, time.time() - start_epoch)
    except Exception:
        return None


def _iso(value):
    return value.isoformat() if value else None


def _db_size_bytes():
    db = settings.DATABASES["default"]
    if "sqlite" not in db.get("ENGINE", ""):
        return None
    try:
        return os.path.getsize(db["NAME"])
    except OSError:
        return None


def _pipeline_status(seconds_since, threshold):
    if seconds_since is None:
        return "unknown"
    if seconds_since <= threshold:
        return "live"
    if seconds_since <= max(threshold * 12, 60):
        return "idle"
    return "stalled"


def collect_system_metrics() -> dict:
    now = timezone.now()
    threshold = getattr(settings, "TRAY_HEARTBEAT_STALE_SECONDS", 5)
    retention_weeks = getattr(settings, "TRAY_HEARTBEAT_RETENTION_WEEKS", 6)
    soft_cap_gb = getattr(settings, "PLATFORM_DB_SOFT_CAP_GB", 2)

    day_ago = now - timedelta(hours=24)
    hour_ago = now - timedelta(hours=1)
    five_min_ago = now - timedelta(minutes=5)
    six_hours_ago = now - timedelta(hours=6)
    retention_cutoff = now - timedelta(weeks=retention_weeks)
    today = timezone.localdate(now)

    # --- Single pass over the last 24h of heartbeat events -------------------
    # Powers ingestion counts, the throughput sparkline, and per-tray downtime.
    stream = list(
        TrayHeartbeatEvent.objects.filter(timestamp__gte=day_ago)
        .values_list("heartbeat__tray_id", "timestamp", "status")
        .order_by("timestamp")
    )

    events_24h = len(stream)
    events_hour = 0
    events_5min = 0
    events_today = 0
    bucket_minutes = 15
    buckets: dict[int, int] = defaultdict(int)
    per_tray_events: dict[str, list] = defaultdict(list)

    for tray_id, ts, status in stream:
        if ts >= hour_ago:
            events_hour += 1
        if ts >= five_min_ago:
            events_5min += 1
        if timezone.localdate(ts) == today:
            events_today += 1
        if ts >= six_hours_ago:
            slot = int((ts - six_hours_ago).total_seconds() // (bucket_minutes * 60))
            buckets[slot] += 1
        per_tray_events[tray_id].append((ts, status))

    total_slots = int(6 * 60 / bucket_minutes)
    ingestion_series = [
        {
            "t": (six_hours_ago + timedelta(minutes=bucket_minutes * i)).isoformat(),
            "count": buckets.get(i, 0),
        }
        for i in range(total_slots)
    ]

    # Per-tray downtime over the window: a DOWN event is immediately followed by
    # its recovery ALIVE, so the gap between them is the outage duration.
    window_seconds = 24 * 3600
    tray_downtime: dict[str, float] = defaultdict(float)
    tray_incidents: dict[str, int] = defaultdict(int)
    for tray_id, events in per_tray_events.items():
        pending_down = None
        for ts, status in events:
            if status == TrayHeartbeatEvent.STATUS_DOWN:
                pending_down = ts
                tray_incidents[tray_id] += 1
            elif status == TrayHeartbeatEvent.STATUS_ALIVE and pending_down is not None:
                tray_downtime[tray_id] += (ts - pending_down).total_seconds()
                pending_down = None
        if pending_down is not None:
            tray_downtime[tray_id] += (now - pending_down).total_seconds()

    # --- Fleet / tray uptime --------------------------------------------------
    # Only count configured trays (those with a TrayStatus, i.e. a known
    # location). Orphan heartbeats with no status row — stale test topics or
    # malformed payloads — are excluded from the table and every aggregate,
    # mirroring how the live dashboard (TrayStatusDataView) filters heartbeats.
    statuses = {s.tray_id: s for s in TrayStatus.objects.all()}
    heartbeats = [hb for hb in TrayHeartbeat.objects.all() if hb.tray_id in statuses]
    trays = []
    online = 0
    active_now = 0
    for hb in sorted(heartbeats, key=lambda h: h.tray_id):
        status_row = statuses.get(hb.tray_id)
        is_alive = hb.is_alive(window_seconds=threshold)
        is_active = bool(status_row and status_row.is_active)
        if is_alive:
            online += 1
        if is_active:
            active_now += 1
        seconds_since = (
            max(0.0, (now - hb.last_seen_at).total_seconds()) if hb.last_seen_at else None
        )
        downtime = min(tray_downtime.get(hb.tray_id, 0.0), window_seconds)
        uptime_pct = round(max(0.0, (window_seconds - downtime) / window_seconds) * 100, 2)
        trays.append(
            {
                "tray_id": hb.tray_id,
                "topic": hb.topic,
                "location": (status_row.location_label if status_row else "") or "Unknown",
                "is_alive": is_alive,
                "is_active": is_active,
                "last_seen_at": _iso(hb.last_seen_at),
                "seconds_since": round(seconds_since, 1) if seconds_since is not None else None,
                "uptime_pct_24h": uptime_pct,
                "down_incidents_24h": tray_incidents.get(hb.tray_id, 0),
            }
        )

    total_trays = len(trays)
    offline = total_trays - online
    availability_pct = round(online / total_trays * 100, 1) if total_trays else 0.0

    latest_hb = max(
        (hb.last_seen_at for hb in heartbeats if hb.last_seen_at), default=None
    )
    seconds_since_last = (
        max(0.0, (now - latest_hb).total_seconds()) if latest_hb else None
    )

    # --- Database + retention -------------------------------------------------
    size_bytes = _db_size_bytes()
    cap_bytes = soft_cap_gb * (1024 ** 3)
    oldest_event = (
        TrayHeartbeatEvent.objects.order_by("timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )
    oldest_age_days = (now - oldest_event).total_seconds() / 86400 if oldest_event else 0
    events_outside_window = (
        TrayHeartbeatEvent.objects.filter(timestamp__lt=retention_cutoff).count()
    )
    window_days = retention_weeks * 7

    # --- Alerts / notifier ----------------------------------------------------
    alerts_24h = TrayStatus.objects.filter(last_alert_sent_at__gte=day_ago).count()
    last_alert = (
        TrayStatus.objects.exclude(last_alert_sent_at__isnull=True)
        .order_by("-last_alert_sent_at")
        .values_list("last_alert_sent_at", flat=True)
        .first()
    )

    container_uptime = _container_uptime_seconds()

    return {
        "server_time": now.isoformat(),
        "process": {
            "app_uptime_seconds": round(time.time() - PROCESS_START_EPOCH),
            "container_uptime_seconds": round(container_uptime) if container_uptime else None,
        },
        "pipeline": {
            "last_heartbeat_at": _iso(latest_hb),
            "seconds_since_last": round(seconds_since_last, 1) if seconds_since_last is not None else None,
            "stale_threshold_seconds": threshold,
            "status": _pipeline_status(seconds_since_last, threshold),
            "events_last_5min": events_5min,
            "events_last_hour": events_hour,
            "events_last_24h": events_24h,
            "events_today": events_today,
            "rate_per_min_recent": round(events_5min / 5, 1),
        },
        "fleet": {
            "total": total_trays,
            "online": online,
            "offline": offline,
            "active_now": active_now,
            "availability_pct": availability_pct,
            "trays": trays,
        },
        "database": {
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 ** 2), 1) if size_bytes else None,
            "soft_cap_gb": soft_cap_gb,
            "usage_pct": round(size_bytes / cap_bytes * 100, 1) if size_bytes and cap_bytes else None,
            "counts": {
                "tray_status": TrayStatus.objects.count(),
                "tray_event": TrayEvent.objects.count(),
                "tray_heartbeat": TrayHeartbeat.objects.count(),
                "tray_heartbeat_event": TrayHeartbeatEvent.objects.count(),
            },
        },
        "retention": {
            "weeks": retention_weeks,
            "window_days": window_days,
            "oldest_event_at": _iso(oldest_event),
            "oldest_age_days": round(oldest_age_days, 1),
            "events_outside_window": events_outside_window,
            "window_usage_pct": round(min(oldest_age_days / window_days, 1) * 100, 1) if window_days else 0.0,
        },
        "alerts": {
            "sent_last_24h": alerts_24h,
            "last_alert_at": _iso(last_alert),
        },
        "ingestion_series": ingestion_series,
    }
