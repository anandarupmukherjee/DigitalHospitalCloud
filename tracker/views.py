import json
import os
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView, View

from .forms import TrayConfigForm, UserCreationWithRoleForm
from .models import TrayEvent, TrayStatus
from services.data_collection_tray.publisher import TrayConfigPublisher
from services.data_storage.repository import record_tray_state
from .utils import ROLE_CHOICES, user_is_manager


class ManagerRequiredMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return user_is_manager(self.request.user)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "tracker/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["tray_statuses"] = TrayStatus.objects.all()
        return context


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
            }
            for tray in sorted(tray_map.values(), key=lambda t: t.tray_id)
        ]
        return JsonResponse({"trays": trays})


class TrayHistoryView(LoginRequiredMixin, ManagerRequiredMixin, TemplateView):
    template_name = "tracker/tray_history.html"

    RANGE_WINDOWS = {
        "day": ("Past day", timedelta(days=1)),
        "week": ("Past week", timedelta(weeks=1)),
        "month": ("Past month", timedelta(days=30)),
        "year": ("Past year", timedelta(days=365)),
    }

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

        range_key = self.request.GET.get("range", "day")
        if range_key not in self.RANGE_WINDOWS:
            range_key = "day"
        range_label, delta = self.RANGE_WINDOWS[range_key]
        end_time = timezone.now()
        start_time = end_time - delta

        events = (
            TrayEvent.objects.filter(tray=selected_tray, timestamp__range=(start_time, end_time))
            .order_by("timestamp")
            if selected_tray
            else TrayEvent.objects.none()
        )

        activation_periods = []
        last_on = None
        open_period = None
        for event in events:
            if event.status == TrayEvent.STATUS_ON:
                last_on = event
            elif event.status == TrayEvent.STATUS_OFF and last_on:
                duration = event.timestamp - last_on.timestamp
                activation_periods.append(
                    {
                        "start": last_on.timestamp,
                        "end": event.timestamp,
                        "duration_hours": duration.total_seconds() / 3600,
                        "duration_minutes": duration.total_seconds() / 60,
                        "is_open": False,
                    }
                )
                last_on = None

        if last_on:
            current_end = min(end_time, timezone.now())
            duration = current_end - last_on.timestamp
            open_period = {
                "start": last_on.timestamp,
                "end": current_end,
                "duration_hours": duration.total_seconds() / 3600,
                "duration_minutes": duration.total_seconds() / 60,
                "is_open": True,
            }
            activation_periods.append(open_period)

        durations = [p["duration_hours"] for p in activation_periods if not p.get("is_open")]
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
                "has_events": events.exists(),
                "chart_data_json": json.dumps(chart_payload),
            }
        )
        return context


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
