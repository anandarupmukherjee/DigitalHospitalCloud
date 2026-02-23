import json
import os
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView, View
from openpyxl import Workbook

from .forms import TrayConfigForm, UserCreationWithRoleForm
from .models import TrayEvent, TrayHeartbeat, TrayHeartbeatEvent, TrayStatus
from .analytics import (
    ActivationWindow,
    compute_activation_window,
    day_hour_matrix,
    histogram_counts,
    hourly_distribution,
    outlier_threshold_minutes,
    percentile,
    queue_series,
)
from services.data_collection_tray.publisher import TrayConfigPublisher
from services.data_storage.repository import record_tray_state
from .utils import ROLE_CHOICES, assign_role, user_is_manager


TRAY_HISTORY_RANGE_WINDOWS = {
    "day": ("Past day", timedelta(days=1)),
    "week": ("Past week", timedelta(weeks=1)),
    "month": ("Past month", timedelta(days=30)),
    "year": ("Past year", timedelta(days=365)),
}


def resolve_history_window(range_key: str):
    if range_key not in TRAY_HISTORY_RANGE_WINDOWS:
        range_key = "day"
    label, delta = TRAY_HISTORY_RANGE_WINDOWS[range_key]
    return range_key, label, delta


class ManagerRequiredMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return user_is_manager(self.request.user)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "tracker/dashboard.html"
    DEFAULT_RANGE = "week"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_input = self.request.GET.get("range", self.DEFAULT_RANGE)
        range_key, range_label, delta = resolve_history_window(range_input)
        end_time = timezone.now()
        start_time = end_time - delta
        location_filter = self.request.GET.get("location", "").strip()

        ignore_weekends = self.request.GET.get("ignore_weekends") == "1"

        trays_qs = TrayStatus.objects.all()
        if location_filter:
            trays_qs = trays_qs.filter(location_label=location_filter)
        trays = list(trays_qs.order_by("tray_id"))

        histories = self._collect_tray_histories(trays, start_time, end_time, ignore_weekends=ignore_weekends)
        completed_periods = self._flatten_completed_periods(histories)

        subtitle = f"{range_label} (weekdays only)" if ignore_weekends else range_label
        volume_chart = self._build_volume_chart(
            completed_periods, start_time, end_time, subtitle, ignore_weekends=ignore_weekends
        )
        duration_trend_chart = self._build_duration_trend_chart(
            completed_periods, start_time, end_time, subtitle, ignore_weekends=ignore_weekends
        )
        outlier_chart = self._build_outlier_chart(
            completed_periods, start_time, end_time, subtitle, ignore_weekends=ignore_weekends
        )
        comparison_chart = self._build_tray_comparison(histories, subtitle)
        scatter_chart = self._build_tray_scatter(histories, delta, subtitle)
        heatmap_chart = self._build_heatmap(completed_periods, subtitle)
        longest_events = self._build_longest_events(completed_periods)

        context.update(
            {
                "tray_statuses": TrayStatus.objects.all(),
                "heartbeat_summary": self._build_heartbeat_summary(),
                "heartbeat_stale_seconds": getattr(settings, "TRAY_HEARTBEAT_STALE_SECONDS", 5),
                "dashboard_range_key": range_key,
                "dashboard_range_label": range_label,
                "dashboard_range_choices": TRAY_HISTORY_RANGE_WINDOWS,
                "dashboard_location_choices": self._location_choices(),
                "selected_location": location_filter,
                "ignore_weekends": ignore_weekends,
                "volume_chart_json": json.dumps(volume_chart) if volume_chart else "",
                "duration_trend_chart_json": json.dumps(duration_trend_chart) if duration_trend_chart else "",
                "outlier_chart_json": json.dumps(outlier_chart) if outlier_chart else "",
                "tray_comparison_chart_json": json.dumps(comparison_chart) if comparison_chart else "",
                "tray_scatter_chart_json": json.dumps(scatter_chart) if scatter_chart else "",
                "time_of_day_chart_json": json.dumps(heatmap_chart) if heatmap_chart else "",
                "longest_events": longest_events,
                "outlier_threshold_minutes": outlier_threshold_minutes(),
            }
        )
        return context

    def _is_weekend(self, dt):
        if not dt:
            return False
        local_dt = timezone.localtime(dt)
        return local_dt.weekday() >= 5

    def _collect_tray_histories(self, trays, start_time, end_time, *, ignore_weekends=False):
        histories = []
        for tray in trays:
            window = compute_activation_window(tray, start_time, end_time)
            activation_periods = window.activation_periods
            if ignore_weekends:
                activation_periods = [
                    period for period in activation_periods if not self._is_weekend(period.get("end"))
                ]
            completed_periods = [p for p in activation_periods if not p.get("is_open")]
            durations = [p["duration_minutes"] for p in completed_periods]
            sorted_minutes = sorted(durations)
            histories.append(
                {
                    "tray": tray,
                    "completed_periods": completed_periods,
                    "durations": durations,
                    "median": percentile(sorted_minutes, 0.5) if sorted_minutes else 0,
                    "p90": percentile(sorted_minutes, 0.9) if sorted_minutes else 0,
                    "count": len(durations),
                    "total_active_minutes": sum(durations),
                }
            )
        return histories

    def _flatten_completed_periods(self, histories):
        periods = []
        for entry in histories:
            tray = entry["tray"]
            location = tray.location_label or "Unknown"
            for period in entry["completed_periods"]:
                periods.append(
                    {
                        **period,
                        "tray": tray,
                        "tray_id": tray.tray_id,
                        "location": location,
                    }
                )
        return periods

    def _window_dates(self, start_time, end_time, *, ignore_weekends=False):
        dates = []
        current = timezone.localtime(start_time).date()
        end_date = timezone.localtime(end_time).date()
        while current <= end_date:
            if not (ignore_weekends and current.weekday() >= 5):
                dates.append(current)
            current += timedelta(days=1)
        if not dates:
            current = timezone.localtime(start_time).date()
            while current <= end_date:
                dates.append(current)
                current += timedelta(days=1)
        return dates

    def _build_volume_chart(self, periods, start_time, end_time, subtitle, *, ignore_weekends=False):
        if not periods:
            return None
        dates = self._window_dates(start_time, end_time, ignore_weekends=ignore_weekends)
        volume_by_day = {date: {} for date in dates}
        tray_locations = {}
        trays_present = set()
        for period in periods:
            local_end = timezone.localtime(period["end"])
            day = local_end.date()
            if day not in volume_by_day:
                continue
            tray_id = period.get("tray_id")
            if not tray_id:
                continue
            trays_present.add(tray_id)
            tray_locations.setdefault(tray_id, period.get("location") or "Unknown")
            volume_by_day[day][tray_id] = volume_by_day[day].get(tray_id, 0) + 1
        if not trays_present:
            return None
        labels = [date.strftime("%b %d") for date in dates]
        tray_list = sorted(trays_present)
        palette = ["#4b9cd3", "#ffad5c", "#6c5ce7", "#2ecc71", "#ff6b6b", "#1c3d5a"]
        datasets = []
        for idx, tray_id in enumerate(tray_list):
            location_label = tray_locations.get(tray_id, "Unknown")
            datasets.append(
                {
                    "label": f"{tray_id} ({location_label})",
                    "data": [volume_by_day[date].get(tray_id, 0) for date in dates],
                    "backgroundColor": palette[idx % len(palette)],
                    "stack": "volume",
                }
            )
        return {"labels": labels, "datasets": datasets, "subtitle": subtitle}

    def _build_duration_trend_chart(self, periods, start_time, end_time, subtitle, *, ignore_weekends=False):
        if not periods:
            return None
        dates = self._window_dates(start_time, end_time, ignore_weekends=ignore_weekends)
        durations_by_day = {date: [] for date in dates}
        for period in periods:
            local_end = timezone.localtime(period["end"])
            day = local_end.date()
            if day in durations_by_day:
                durations_by_day[day].append(period["duration_minutes"])
        labels = [date.strftime("%b %d") for date in dates]
        median = []
        p90 = []
        for date in dates:
            durations = sorted(durations_by_day[date])
            median.append(round(percentile(durations, 0.5), 2) if durations else 0)
            p90.append(round(percentile(durations, 0.9), 2) if durations else 0)
        if not any(median) and not any(p90):
            return None
        return {"labels": labels, "median": median, "p90": p90, "subtitle": subtitle}

    def _build_outlier_chart(self, periods, start_time, end_time, subtitle, *, ignore_weekends=False):
        if not periods:
            return None
        threshold = outlier_threshold_minutes()
        dates = self._window_dates(start_time, end_time, ignore_weekends=ignore_weekends)
        durations_by_day = {date: [] for date in dates}
        for period in periods:
            local_end = timezone.localtime(period["end"])
            day = local_end.date()
            if day in durations_by_day:
                durations_by_day[day].append(period["duration_minutes"])
        labels = [date.strftime("%b %d") for date in dates]
        rates = []
        numerators = []
        denominators = []
        for date in dates:
            durations = durations_by_day[date]
            denom = len(durations)
            denominators.append(denom)
            outliers = len([value for value in durations if value > threshold])
            numerators.append(outliers)
            rate = round(outliers / denom * 100, 2) if denom else 0
            rates.append(rate)
        if not any(denominators):
            return None
        return {
            "labels": labels,
            "rates": rates,
            "numerators": numerators,
            "denominators": denominators,
            "subtitle": subtitle,
        }

    def _build_tray_comparison(self, histories, subtitle):
        ranked = [entry for entry in histories if entry["count"]]
        if not ranked:
            return None
        ranked.sort(key=lambda entry: entry["median"], reverse=True)
        labels = [
            f"{entry['tray'].tray_id} ({entry['tray'].location_label or 'Unknown'})"
            for entry in ranked
        ]
        return {
            "labels": labels,
            "median": [round(entry["median"], 2) for entry in ranked],
            "p90": [round(entry["p90"], 2) for entry in ranked],
            "counts": [entry["count"] for entry in ranked],
            "subtitle": subtitle,
        }

    def _build_tray_scatter(self, histories, delta, subtitle):
        window_minutes = delta.total_seconds() / 60 or 1
        points = []
        for entry in histories:
            if not entry["count"]:
                continue
            utilization = (entry["total_active_minutes"] / window_minutes) * 100
            points.append(
                {
                    "tray": entry["tray"].tray_id,
                    "location": entry["tray"].location_label or "Unknown",
                    "utilization": round(utilization, 2),
                    "median": round(entry["median"], 2),
                    "p90": round(entry["p90"], 2),
                    "count": entry["count"],
                }
            )
        if not points:
            return None
        return {"points": points, "subtitle": subtitle}

    def _build_heatmap(self, periods, subtitle):
        if not periods:
            return None
        matrix = day_hour_matrix(periods)
        if not any(point["count"] for point in matrix):
            return None
        return {"points": matrix, "subtitle": subtitle}

    def _build_longest_events(self, periods, limit=15):
        longest = sorted(periods, key=lambda period: period["duration_minutes"], reverse=True)[:limit]
        rows = []
        for period in longest:
            rows.append(
                {
                    "tray_id": period["tray_id"],
                    "location": period["location"],
                    "start": timezone.localtime(period["start"]),
                    "end": timezone.localtime(period["end"]),
                    "minutes": round(period["duration_minutes"], 2),
                }
            )
        return rows

    def _location_choices(self):
        labels = (
            TrayStatus.objects.exclude(location_label__isnull=True)
            .exclude(location_label__exact="")
            .values_list("location_label", flat=True)
            .distinct()
        )
        return sorted(labels)

    def _build_heartbeat_summary(self):
        threshold = getattr(settings, "TRAY_HEARTBEAT_STALE_SECONDS", 5)
        latest = (
            TrayHeartbeat.objects.exclude(last_seen_at__isnull=True)
            .order_by("-last_seen_at")
            .first()
        )
        if not latest:
            return {
                "is_alive": False,
                "last_seen_at": None,
                "tray_id": None,
                "threshold_seconds": threshold,
            }
        return {
            "is_alive": latest.is_alive(window_seconds=threshold),
            "last_seen_at": latest.last_seen_at,
            "tray_id": latest.tray_id,
            "topic": latest.topic,
            "threshold_seconds": threshold,
        }


class TrayStatusDataView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        tray_map = {}
        queryset = (
            TrayStatus.objects.exclude(latitude__isnull=True)
            .exclude(longitude__isnull=True)
            .order_by("-updated_at")
        )
        for tray in queryset:
            if tray.tray_id not in tray_map:
                tray_map[tray.tray_id] = tray
        known_tray_ids = set(TrayStatus.objects.values_list("tray_id", flat=True))
        heartbeats = list(TrayHeartbeat.objects.all())
        heartbeat_map = {hb.unique_key: hb for hb in heartbeats}
        threshold = getattr(settings, "TRAY_HEARTBEAT_STALE_SECONDS", 5)
        visible_heartbeats = [hb for hb in heartbeats if hb.tray_id in known_tray_ids]
        trays = [
            {
                "key": tray.unique_key,
                "tray_id": tray.tray_id,
                "topic": tray.topic,
                "location_label": tray.location_label,
                "latitude": tray.latitude,
                "longitude": tray.longitude,
                "is_active": tray.is_active,
                "last_on_at": tray.activated_at.isoformat()
                if tray.activated_at
                else None,
                "activated_at": tray.activated_at.isoformat()
                if tray.activated_at
                else None,
                "deactivated_at": tray.deactivated_at.isoformat()
                if tray.deactivated_at
                else None,
                "updated_at": tray.updated_at.isoformat(),
                "heartbeat": self._serialize_heartbeat(
                    heartbeat_map.get(tray.unique_key), threshold
                ),
            }
            for tray in sorted(tray_map.values(), key=lambda t: t.tray_id)
        ]
        heartbeat_records = [
            {
                "key": hb.unique_key,
                "tray_id": hb.tray_id,
                "topic": hb.topic,
                "last_seen_at": hb.last_seen_at.isoformat() if hb.last_seen_at else None,
                "is_alive": hb.is_alive(window_seconds=threshold),
            }
            for hb in visible_heartbeats
        ]
        return JsonResponse(
            {
                "trays": trays,
                "heartbeat": {
                    "summary": self._summarize_heartbeats(visible_heartbeats, threshold),
                    "records": heartbeat_records,
                },
            }
        )

    def _serialize_heartbeat(self, heartbeat: TrayHeartbeat | None, threshold: int):
        if not heartbeat:
            return None
        return {
            "last_seen_at": heartbeat.last_seen_at.isoformat()
            if heartbeat.last_seen_at
            else None,
            "is_alive": heartbeat.is_alive(window_seconds=threshold),
        }

    def _summarize_heartbeats(self, heartbeats, threshold: int):
        relevant = [hb for hb in heartbeats if hb.last_seen_at]
        if not relevant:
            return {
                "is_alive": False,
                "last_seen_at": None,
                "tray_id": None,
                "threshold_seconds": threshold,
            }
        latest = max(relevant, key=lambda hb: hb.last_seen_at)
        return {
            "is_alive": latest.is_alive(window_seconds=threshold),
            "last_seen_at": latest.last_seen_at.isoformat(),
            "tray_id": latest.tray_id,
            "topic": latest.topic,
            "threshold_seconds": threshold,
        }


class TrayHistoryView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    template_name = "tracker/tray_history.html"
    RANGE_WINDOWS = TRAY_HISTORY_RANGE_WINDOWS

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trays = TrayStatus.objects.order_by("tray_id")
        tray_param = self.request.GET.get("tray")

        selected_tray = None
        if tray_param:
            selected_tray = trays.filter(id=tray_param).first()
            if selected_tray is None:
                selected_tray = trays.filter(tray_id=tray_param).first()
        else:
            selected_tray = trays.first()
            tray_param = str(selected_tray.id) if selected_tray else None

        range_input = self.request.GET.get("range", "day")
        range_key, range_label, delta = resolve_history_window(range_input)
        end_time = timezone.now()
        start_time = end_time - delta

        activation_periods = []
        events = []
        open_period = None
        if selected_tray:
            window_data = compute_activation_window(selected_tray, start_time, end_time)
            activation_periods = window_data.activation_periods
            events = window_data.events
            open_period = window_data.open_period

        completed_periods = [p for p in activation_periods if not p.get("is_open")]
        durations = [p["duration_hours"] for p in completed_periods]
        total_activations = len(durations)
        avg_duration = sum(durations) / total_activations if total_activations else 0
        longest = max(durations) if durations else 0
        total_active_hours = sum(durations)
        window_hours = delta.total_seconds() / 3600
        utilization = (total_active_hours / window_hours * 100) if window_hours else 0

        duration_minutes = [p["duration_minutes"] for p in completed_periods]
        sorted_minutes = sorted(duration_minutes)
        median_duration = percentile(sorted_minutes, 0.5) if sorted_minutes else 0
        p90_duration = percentile(sorted_minutes, 0.9) if sorted_minutes else 0
        longest_minutes = max(duration_minutes) if duration_minutes else 0
        threshold_minutes = outlier_threshold_minutes()

        duration_trend_payload = None
        if activation_periods:
            duration_trend_payload = {
                "subtitle": range_label,
                "points": [
                    {
                        "start": period["start"].isoformat(),
                        "end": period["end"].isoformat(),
                        "minutes": round(period["duration_minutes"], 2),
                        "is_open": period.get("is_open", False),
                        "is_outlier": period["duration_minutes"] > threshold_minutes,
                    }
                    for period in activation_periods
                ],
                "median": round(median_duration, 2),
                "threshold": threshold_minutes,
            }

        histogram_payload = None
        if duration_minutes:
            histogram_payload = {
                "subtitle": range_label,
                "buckets": histogram_counts(duration_minutes),
                "p50": round(median_duration, 2),
                "p90": round(p90_duration, 2),
                "max": round(longest_minutes, 2),
            }

        hourly_payload = None
        hourly_stats = hourly_distribution(completed_periods)
        if any(stat["count"] for stat in hourly_stats):
            hourly_payload = {
                "subtitle": range_label,
                "hours": [stat["hour"] for stat in hourly_stats],
                "median": [stat["median"] for stat in hourly_stats],
                "counts": [stat["count"] for stat in hourly_stats],
            }

        timeline_payload = None
        if completed_periods:
            timeline_payload = {
                "subtitle": range_label,
                "window_start": start_time.isoformat(),
                "window_end": end_time.isoformat(),
                "labels": [
                    timezone.localtime(period["start"]).strftime("%b %d %H:%M")
                    for period in completed_periods
                ],
                "ranges": [
                    {
                        "start": period["start"].isoformat(),
                        "end": period["end"].isoformat(),
                        "minutes": round(period["duration_minutes"], 2),
                        "is_outlier": period["duration_minutes"] > threshold_minutes,
                    }
                    for period in completed_periods
                ],
            }

        queue_payload = None
        queue_points = queue_series(events, end_time=end_time) if events else []
        if queue_points:
            queue_payload = {
                "subtitle": range_label,
                "points": queue_points,
            }

        outlier_rows = [
            {
                "start": timezone.localtime(period["start"]),
                "end": timezone.localtime(period["end"]),
                "minutes": round(period["duration_minutes"], 2),
                "location": (selected_tray.location_label if selected_tray else "") or "Unknown",
            }
            for period in completed_periods
            if period["duration_minutes"] > threshold_minutes
        ]

        snapshot = None
        if selected_tray:
            snapshot = {
                "tray_id": selected_tray.tray_id,
                "topic": selected_tray.topic,
                "location": selected_tray.location_label or "Unknown location",
                "is_active": selected_tray.is_active,
                "activated_at": selected_tray.activated_at,
                "deactivated_at": selected_tray.deactivated_at,
                "last_update": selected_tray.updated_at,
            }
        heartbeat_status = None
        heartbeat_events_page = None
        heartbeat_events = []
        heartbeat_events_total = 0
        heartbeat_prev_url = None
        heartbeat_next_url = None
        if selected_tray:
            heartbeat = (
                TrayHeartbeat.objects.filter(tray_id=selected_tray.tray_id)
                .order_by("-last_seen_at")
                .first()
            )
            heartbeat_events_qs = TrayHeartbeatEvent.objects.filter(
                heartbeat__tray_id=selected_tray.tray_id,
                timestamp__range=(start_time, end_time),
            ).order_by("-timestamp")
            heartbeat_page_size = getattr(settings, "TRAY_HEARTBEAT_PAGE_SIZE", 200)
            heartbeat_paginator = Paginator(heartbeat_events_qs, heartbeat_page_size)
            heartbeat_page_number = self.request.GET.get("heartbeat_page") or 1
            heartbeat_events_page = heartbeat_paginator.get_page(heartbeat_page_number)
            heartbeat_events = list(heartbeat_events_page)
            heartbeat_events_total = heartbeat_paginator.count

            def build_heartbeat_page_url(page_number: int) -> str:
                params = {"range": range_key, "heartbeat_page": page_number}
                if tray_param:
                    params["tray"] = tray_param
                return f"?{urlencode(params)}"

            if heartbeat_events_page.has_previous():
                heartbeat_prev_url = build_heartbeat_page_url(
                    heartbeat_events_page.previous_page_number()
                )
            if heartbeat_events_page.has_next():
                heartbeat_next_url = build_heartbeat_page_url(
                    heartbeat_events_page.next_page_number()
                )
            if heartbeat:
                heartbeat_status = {
                    "tray_id": heartbeat.tray_id,
                    "topic": heartbeat.topic,
                    "last_seen_at": heartbeat.last_seen_at,
                    "is_alive": heartbeat.is_alive(),
                    "threshold_seconds": getattr(settings, "TRAY_HEARTBEAT_STALE_SECONDS", 5),
                }

        context.update(
            {
                "trays": trays,
                "selected_tray": selected_tray,
                "selected_tray_value": tray_param,
                "events": events,
                "range_key": range_key,
                "range_choices": self.RANGE_WINDOWS,
                "range_label": range_label,
                "activation_periods": activation_periods,
                "stats": {
                    "total_activations": total_activations,
                    "avg_duration": avg_duration,
                    "longest_duration": longest,
                    "total_active_hours": total_active_hours,
                    "utilization": utilization,
                    "open_duration": open_period["duration_hours"] if open_period else 0,
                    "median_duration": median_duration,
                    "p90_duration": p90_duration,
                },
                "snapshot": snapshot,
                "heartbeat_status": heartbeat_status,
                "heartbeat_events": heartbeat_events,
                "heartbeat_events_page": heartbeat_events_page,
                "heartbeat_events_total": heartbeat_events_total,
                "heartbeat_prev_url": heartbeat_prev_url,
                "heartbeat_next_url": heartbeat_next_url,
                "has_events": bool(events),
                "outlier_threshold_minutes": threshold_minutes,
                "duration_trend_json": json.dumps(duration_trend_payload) if duration_trend_payload else "",
                "duration_histogram_json": json.dumps(histogram_payload) if histogram_payload else "",
                "hourly_distribution_json": json.dumps(hourly_payload) if hourly_payload else "",
                "timeline_json": json.dumps(timeline_payload) if timeline_payload else "",
                "queue_series_json": json.dumps(queue_payload) if queue_payload else "",
                "outlier_events": outlier_rows,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        tray_param = request.POST.get("tray")
        if not tray_param:
            messages.error(request, "Please select a tray to delete.")
            return redirect("tray-history")

        tray = (
            TrayStatus.objects.filter(id=tray_param).first()
            or TrayStatus.objects.filter(tray_id=tray_param).first()
        )

        if not tray:
            messages.error(request, "Tray not found or already deleted.")
            return redirect("tray-history")

        tray_label = tray.tray_id
        tray.delete()
        messages.success(request, f"Tray {tray_label} and its history were deleted.")
        return redirect("tray-history")


class TrayReportDownloadView(LoginRequiredMixin, ManagerRequiredMixin, View):
    """Download an Excel report with collection and heartbeat events."""

    def get(self, request, pk, *args, **kwargs):
        tray = get_object_or_404(TrayStatus, pk=pk)
        range_key_input = request.GET.get("range", "day")
        _, _, delta = resolve_history_window(range_key_input)
        end_time = timezone.now()
        start_time = end_time - delta

        collection_events = TrayEvent.objects.filter(
            tray=tray, timestamp__range=(start_time, end_time)
        ).order_by("timestamp")

        heartbeat = (
            TrayHeartbeat.objects.filter(tray_id=tray.tray_id)
            .order_by("-last_seen_at")
            .first()
        )
        heartbeat_events = list(
            TrayHeartbeatEvent.objects.filter(
                heartbeat__tray_id=tray.tray_id,
                timestamp__range=(start_time, end_time),
            ).order_by("timestamp")
        )

        workbook = Workbook()
        collection_sheet = workbook.active
        collection_sheet.title = "collection"
        collection_sheet.append(["Timestamp", "Status", "Topic"])
        for event in collection_events:
            collection_sheet.append(
                [
                    timezone.localtime(event.timestamp).isoformat(),
                    event.get_status_display(),
                    event.topic or "",
                ]
            )

        heartbeat_sheet = workbook.create_sheet("alive")
        heartbeat_sheet.append(["Timestamp", "Status", "Note"])
        for hb_event in heartbeat_events:
            heartbeat_sheet.append(
                [
                    timezone.localtime(hb_event.timestamp).isoformat(),
                    hb_event.get_status_display(),
                    hb_event.note or "",
                ]
            )

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        timestamp_slug = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{tray.tray_id}_{timestamp_slug}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        workbook.save(response)
        return response


class TopicManagementView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    template_name = "tracker/topic_management.html"

    def _available_topics(self):
        topics = TrayStatus.objects.values_list("topic", flat=True).distinct()
        return sorted({topic or "" for topic in topics})

    def _topic_label(self, topic: str | None) -> str:
        if topic is None:
            return "No topic selected"
        return topic or "Blank topic"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topics = self._available_topics()
        requested_topic = self.request.GET.get("topic")
        selected_topic = requested_topic if requested_topic in topics else None
        if selected_topic is None and topics:
            selected_topic = topics[0]

        last_event = None
        last_payload_pretty = None
        topic_trays = TrayStatus.objects.none()
        if selected_topic is not None:
            last_event = (
                TrayEvent.objects.select_related("tray")
                .filter(topic=selected_topic)
                .order_by("-timestamp")
                .first()
            )
            if last_event:
                last_payload_pretty = json.dumps(last_event.payload, indent=2, sort_keys=True)
            topic_trays = TrayStatus.objects.filter(topic=selected_topic).order_by("tray_id")

        context.update(
            {
                "topics": topics,
                "selected_topic": selected_topic,
                "selected_topic_label": self._topic_label(selected_topic),
                "last_event": last_event,
                "last_payload_pretty": last_payload_pretty,
                "topic_trays": topic_trays,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        topic_to_delete = request.POST.get("topic")
        if topic_to_delete is None:
            messages.error(request, "Select a topic to delete.")
            return redirect("topic-management")

        statuses = TrayStatus.objects.filter(topic=topic_to_delete)
        count = statuses.count()
        if count == 0:
            messages.info(request, "No trackers found for that topic.")
        else:
            statuses.delete()
            messages.success(
                request,
                f"Removed {count} tracker{'s' if count != 1 else ''} for {self._topic_label(topic_to_delete)}.",
            )
        return redirect("topic-management")


class UserManagementView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    template_name = "tracker/user_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        User = get_user_model()
        context["form"] = context.get("form") or UserCreationWithRoleForm()
        users = list(User.objects.order_by("username"))
        for user in users:
            user.current_role = self._resolve_role_key(user)
        context["users"] = users
        context["role_choices"] = dict(ROLE_CHOICES)
        context["role_choices_list"] = ROLE_CHOICES
        return context

    def post(self, request, *args, **kwargs):
        if request.user.is_superuser:
            action = request.POST.get("action")
            if action == "update-role":
                return self._handle_role_change(request)
            if action == "delete-user":
                return self._handle_user_delete(request)
        form = UserCreationWithRoleForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Created user {user.username}.")
            return redirect("user-management")
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def _handle_role_change(self, request):
        user_id = request.POST.get("user_id")
        role = request.POST.get("role")
        User = get_user_model()
        user = User.objects.filter(id=user_id).first()
        if not user:
            messages.error(request, "User not found.")
            return redirect("user-management")
        if user.is_superuser:
            messages.error(request, "Cannot modify roles for superusers.")
            return redirect("user-management")
        valid_roles = dict(ROLE_CHOICES)
        if role not in valid_roles:
            messages.error(request, "Invalid role selection.")
            return redirect("user-management")
        assign_role(user, role)
        messages.success(request, f"Updated role for {user.username} to {valid_roles[role]}.")
        return redirect("user-management")

    def _handle_user_delete(self, request):
        user_id = request.POST.get("user_id")
        User = get_user_model()
        user = User.objects.filter(id=user_id).first()
        if not user:
            messages.error(request, "User not found.")
            return redirect("user-management")
        if user.is_superuser:
            messages.error(request, "Cannot delete a superuser account.")
            return redirect("user-management")
        if user.id == request.user.id:
            messages.error(request, "You cannot delete your own account.")
            return redirect("user-management")
        username = user.username
        user.delete()
        messages.success(request, f"Deleted user {username}.")
        return redirect("user-management")

    def _resolve_role_key(self, user):
        for role_value, _ in ROLE_CHOICES:
            if user.groups.filter(name=role_value).exists():
                return role_value
        return ""


class ConfigureTraysView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    template_name = "tracker/configure_trays.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = context.get("form") or TrayConfigForm()
        context["broker_host"] = os.environ.get("MQTT_BROKER_HOST", "broker.hivemq.com")
        publisher = TrayConfigPublisher()
        context["config_topics"] = publisher.available_topic_templates()
        return context

    def post(self, request, *args, **kwargs):
        form = TrayConfigForm(request.POST)
        if form.is_valid():
            payload = form.payload()
            publisher = TrayConfigPublisher()
            try:
                publisher.publish(payload)
            except Exception as exc:
                messages.error(request, f"Failed to send configuration: {exc}")
            else:
                topics = publisher.resolve_topics(payload["pico_id"])
                messages.success(
                    request,
                    f"Sent config to {', '.join(topics)} targeting {payload['pico_id']}.",
                )
                sensor_topic_template = os.environ.get(
                    "MQTT_STATUS_TOPIC_TEMPLATE", "MET/hospital/sensors/{tray_id}"
                )
                sensor_topic = sensor_topic_template.format(tray_id=payload["tray_id"])
                try:
                    record_tray_state(
                        payload["tray_id"],
                        topic=sensor_topic,
                        location_label=payload["location_label"],
                        latitude=payload["latitude"],
                        longitude=payload["longitude"],
                        is_active=False,
                        payload={**payload, "source": "configure-form"},
                    )
                except Exception as exc:
                    messages.warning(
                        request,
                        f"Config sent but failed to store tracker snapshot locally: {exc}",
                    )
                TrayStatus.objects.filter(tray_id=payload["tray_id"], topic__in=topics).delete()
                return redirect("configure-trays")
        context = self.get_context_data(form=form)
        return self.render_to_response(context)
