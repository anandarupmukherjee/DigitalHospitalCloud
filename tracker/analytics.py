import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from django.conf import settings
from django.utils import timezone

from .models import TrayEvent, TrayStatus


DURATION_BUCKETS: Sequence[Tuple[int, Optional[int]]] = (
    (0, 30),
    (30, 60),
    (60, 120),
    (120, 240),
    (240, None),
)


def outlier_threshold_minutes() -> int:
    return getattr(settings, "TRAY_OUTLIER_THRESHOLD_MINUTES", 240)


def percentile(sorted_values: Sequence[float], fraction: float) -> float:
    if not sorted_values:
        return 0
    if fraction <= 0:
        return sorted_values[0]
    if fraction >= 1:
        return sorted_values[-1]
    idx = (len(sorted_values) - 1) * fraction
    lower = math.floor(idx)
    upper = math.ceil(idx)
    if lower == upper:
        return sorted_values[int(idx)]
    weight = idx - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


@dataclass
class ActivationWindow:
    events: List[TrayEvent]
    activation_periods: List[Dict]
    open_period: Optional[Dict]


def _build_activation_periods_from_events(
    events: Iterable[TrayEvent],
    *,
    carry_in_event: Optional[TrayEvent],
    start_time,
    end_time,
) -> ActivationWindow:
    activation_periods: List[Dict] = []
    last_on: Optional[TrayEvent] = None
    if carry_in_event and carry_in_event.status == TrayEvent.STATUS_ON:
        last_on = carry_in_event
    open_period: Optional[Dict] = None
    for event in events:
        if event.status == TrayEvent.STATUS_ON:
            last_on = event
        elif event.status == TrayEvent.STATUS_OFF and last_on:
            period_start = max(last_on.timestamp, start_time)
            if period_start >= event.timestamp:
                last_on = None
                continue
            duration = event.timestamp - period_start
            activation_periods.append(
                {
                    "start": period_start,
                    "end": event.timestamp,
                    "duration_hours": duration.total_seconds() / 3600,
                    "duration_minutes": duration.total_seconds() / 60,
                    "is_open": False,
                    "started_before_window": last_on.timestamp < start_time,
                }
            )
            last_on = None
    if last_on:
        current_end = end_time
        period_start = max(last_on.timestamp, start_time)
        if current_end > period_start:
            duration = current_end - period_start
            open_period = {
                "start": period_start,
                "end": current_end,
                "duration_hours": duration.total_seconds() / 3600,
                "duration_minutes": duration.total_seconds() / 60,
                "is_open": True,
                "started_before_window": last_on.timestamp < start_time,
            }
            activation_periods.append(open_period)
    return ActivationWindow(list(events), activation_periods, open_period)


def compute_activation_window(tray: TrayStatus, start_time, end_time) -> ActivationWindow:
    if not tray:
        return ActivationWindow([], [], None)
    events_qs = TrayEvent.objects.filter(
        tray=tray, timestamp__range=(start_time, end_time)
    ).order_by("timestamp")
    carry_in_event = (
        TrayEvent.objects.filter(tray=tray, timestamp__lt=start_time)
        .order_by("-timestamp")
        .first()
    )
    return _build_activation_periods_from_events(
        events_qs,
        carry_in_event=carry_in_event,
        start_time=start_time,
        end_time=end_time,
    )


def histogram_counts(
    durations: Sequence[float],
    buckets: Sequence[Tuple[int, Optional[int]]] = DURATION_BUCKETS,
) -> List[Dict]:
    histogram: List[Dict] = []
    for lower, upper in buckets:
        count = 0
        for value in durations:
            if value < lower:
                continue
            if upper is None and value >= lower:
                count += 1
            elif lower <= value < upper:
                count += 1
        label = f"{lower}–{upper}" if upper is not None else f"{lower}+"
        histogram.append({"label": label, "count": count, "lower": lower, "upper": upper})
    return histogram


def hourly_distribution(activation_periods: Sequence[Dict]) -> List[Dict]:
    per_hour: Dict[int, List[float]] = defaultdict(list)
    for period in activation_periods:
        if period.get("is_open"):
            continue
        start_local = timezone.localtime(period["start"])
        per_hour[start_local.hour].append(period["duration_minutes"])
    results = []
    for hour in range(24):
        durations = sorted(per_hour.get(hour, []))
        results.append(
            {
                "hour": hour,
                "median": round(percentile(durations, 0.5), 2) if durations else 0,
                "count": len(durations),
            }
        )
    return results


def queue_series(events: Sequence[TrayEvent], *, end_time) -> List[Dict]:
    series: List[Dict] = []
    current_start = None
    for event in events:
        timestamp = event.timestamp
        if event.status == TrayEvent.STATUS_ON:
            current_start = timestamp
            series.append({"timestamp": timestamp.isoformat(), "minutes": 0})
        elif event.status == TrayEvent.STATUS_OFF and current_start:
            duration_minutes = (timestamp - current_start).total_seconds() / 60
            series.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "minutes": round(duration_minutes, 2),
                }
            )
            current_start = None
    if current_start:
        duration_minutes = (end_time - current_start).total_seconds() / 60
        series.append(
            {
                "timestamp": end_time.isoformat(),
                "minutes": round(duration_minutes, 2),
                "is_open": True,
            }
        )
    return series


def day_hour_matrix(periods: Sequence[Dict]) -> List[Dict]:
    matrix: Dict[Tuple[int, int], List[float]] = defaultdict(list)
    for period in periods:
        if period.get("is_open"):
            continue
        local_start = timezone.localtime(period["start"])
        matrix[(local_start.weekday(), local_start.hour)].append(period["duration_minutes"])
    points = []
    for weekday in range(7):
        for hour in range(24):
            durations = sorted(matrix.get((weekday, hour), []))
            points.append(
                {
                    "weekday": weekday,
                    "hour": hour,
                    "median": round(percentile(durations, 0.5), 2) if durations else 0,
                    "count": len(durations),
                }
            )
    return points
