import json
import math
import os
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView, View
from openpyxl import Workbook

from .forms import TrayConfigForm, UserCreationWithRoleForm
from .models import TrayEvent, TrayHeartbeat, TrayHeartbeatEvent, TrayStatus
from services.data_collection_tray.publisher import TrayConfigPublisher
from services.data_storage.repository import record_tray_state
from .utils import ROLE_CHOICES, user_is_manager


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


def _percentile(sorted_values, fraction: float) -> float:
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


class ManagerRequiredMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return user_is_manager(self.request.user)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "tracker/dashboard.html"
    COLLECTION_WINDOW = timedelta(days=7)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tray_statuses"] = TrayStatus.objects.all()
        chart_payload = self._build_dashboard_collection_chart()
        context["dashboard_summary_chart_label"] = f"last {self.COLLECTION_WINDOW.days} days"
        context["dashboard_summary_chart_json"] = json.dumps(chart_payload) if chart_payload else ""
        context["heartbeat_summary"] = self._build_heartbeat_summary()
        context["heartbeat_stale_seconds"] = getattr(settings, "TRAY_HEARTBEAT_STALE_SECONDS", 5)
        return context

    def _build_dashboard_collection_chart(self):
        end_time = timezone.now()
        start_time = end_time - self.COLLECTION_WINDOW
        tray_points = []
        trays = TrayStatus.objects.order_by("tray_id")
        for tray in trays:
            events = list(
                TrayEvent.objects.filter(tray=tray, timestamp__range=(start_time, end_time)).order_by("timestamp")
            )
            carry_in = (
                TrayEvent.objects.filter(tray=tray, timestamp__lt=start_time)
                .order_by("-timestamp")
                .first()
            )

            last_on = None
            if carry_in and carry_in.status == TrayEvent.STATUS_ON:
                last_on = carry_in

            duration_minutes = []
            for event in events:
                if event.status == TrayEvent.STATUS_ON:
                    last_on = event
                elif event.status == TrayEvent.STATUS_OFF and last_on:
                    period_start = max(last_on.timestamp, start_time)
                    if period_start >= event.timestamp:
                        last_on = None
                        continue
                    duration = event.timestamp - period_start
                    duration_minutes.append(duration.total_seconds() / 60)
                    last_on = None

            if not duration_minutes:
                continue

            sorted_minutes = sorted(duration_minutes)
            tray_points.append(
                {
                    "tray_id": tray.tray_id,
                    "avg": round(sum(sorted_minutes) / len(sorted_minutes), 2),
                    "min": round(sorted_minutes[0], 2),
                    "max": round(sorted_minutes[-1], 2),
                    "q1": round(_percentile(sorted_minutes, 0.25), 2),
                    "q3": round(_percentile(sorted_minutes, 0.75), 2),
                }
            )

        if not tray_points:
            return None

        return {
            "labels": [point["tray_id"] for point in tray_points],
            "avg_minutes": [point["avg"] for point in tray_points],
            "min_minutes": [point["min"] for point in tray_points],
            "max_minutes": [point["max"] for point in tray_points],
            "q1_minutes": [point["q1"] for point in tray_points],
            "q3_minutes": [point["q3"] for point in tray_points],
        }

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

        events_qs = (
            TrayEvent.objects.filter(tray=selected_tray, timestamp__range=(start_time, end_time))
            .order_by("timestamp")
            if selected_tray
            else TrayEvent.objects.none()
        )
        events = list(events_qs)

        carry_in_event = None
        if selected_tray:
            carry_in_event = (
                TrayEvent.objects.filter(tray=selected_tray, timestamp__lt=start_time)
                .order_by("-timestamp")
                .first()
            )

        activation_periods = []
        last_on = None
        if carry_in_event and carry_in_event.status == TrayEvent.STATUS_ON:
            last_on = carry_in_event
        open_period = None
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

        completed_periods = [p for p in activation_periods if not p.get("is_open")]
        durations = [p["duration_hours"] for p in completed_periods]
        total_activations = len(durations)
        avg_duration = sum(durations) / total_activations if total_activations else 0
        longest = max(durations) if durations else 0
        total_active_hours = sum(durations)
        window_hours = delta.total_seconds() / 3600
        utilization = (total_active_hours / window_hours * 100) if window_hours else 0

        chart_payload = {
            "labels": [p["end"].isoformat() for p in activation_periods],
            "data": [round(p["duration_minutes"], 2) for p in activation_periods],
        }

        duration_minutes = [p["duration_minutes"] for p in completed_periods]
        summary_chart_payload = None
        if duration_minutes:
            sorted_minutes = sorted(duration_minutes)
            summary_chart_payload = {
                "avg_minutes": round(sum(sorted_minutes) / len(sorted_minutes), 2),
                "min_minutes": round(sorted_minutes[0], 2),
                "max_minutes": round(sorted_minutes[-1], 2),
                "q1_minutes": round(_percentile(sorted_minutes, 0.25), 2),
                "q3_minutes": round(_percentile(sorted_minutes, 0.75), 2),
            }

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
        heartbeat_events = []
        if selected_tray:
            heartbeat = (
                TrayHeartbeat.objects.filter(tray_id=selected_tray.tray_id)
                .order_by("-last_seen_at")
                .first()
            )
            heartbeat_events = list(
                TrayHeartbeatEvent.objects.filter(
                    heartbeat__tray_id=selected_tray.tray_id,
                    timestamp__range=(start_time, end_time),
                ).order_by("-timestamp")
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
                },
                "snapshot": snapshot,
                "heartbeat_status": heartbeat_status,
                "heartbeat_events": heartbeat_events,
                "has_events": bool(events),
                "chart_data_json": json.dumps(chart_payload),
                "summary_chart_data_json": json.dumps(summary_chart_payload) if summary_chart_payload else "",
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
        context["users"] = User.objects.order_by("username")
        context["role_choices"] = dict(ROLE_CHOICES)
        return context

    def post(self, request, *args, **kwargs):
        form = UserCreationWithRoleForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Created user {user.username}.")
            return redirect("user-management")
        context = self.get_context_data(form=form)
        return self.render_to_response(context)


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
