from django.contrib import admin

from .models import TrayEvent, TrayStatus


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
