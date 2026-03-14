from django.contrib import admin

from .models import TrayEvent, TrayHeartbeat, TrayHeartbeatEvent, TrayStatus


@admin.register(TrayStatus)
class TrayStatusAdmin(admin.ModelAdmin):
    list_display = (
        "tray_id",
        "location_label",
        "latitude",
        "longitude",
        "is_active",
        "activated_at",
        "deactivated_at",
        "updated_at",
    )
    search_fields = ("tray_id", "location_label")
    list_filter = ("is_active",)


@admin.register(TrayEvent)
class TrayEventAdmin(admin.ModelAdmin):
    list_display = ("tray", "status", "timestamp", "topic")
    list_filter = ("status", "topic")
    search_fields = ("tray__tray_id", "topic")


@admin.register(TrayHeartbeat)
class TrayHeartbeatAdmin(admin.ModelAdmin):
    list_display = ("tray_id", "topic", "last_seen_at", "updated_at")
    search_fields = ("tray_id", "topic")


@admin.register(TrayHeartbeatEvent)
class TrayHeartbeatEventAdmin(admin.ModelAdmin):
    list_display = ("heartbeat", "status", "timestamp", "note")
    list_filter = ("status",)
    search_fields = ("heartbeat__tray_id", "note")
