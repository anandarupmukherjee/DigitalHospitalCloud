from django.db import models


class TrayStatus(models.Model):
    """Represents the latest known position and state of a tray tracker."""

    tray_id = models.CharField(max_length=64)
    topic = models.CharField(max_length=255, blank=True)
    location_label = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    last_payload = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tray_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tray_id", "topic"], name="unique_tray_topic"
            )
        ]

    def __str__(self):
        return f"{self.tray_id} ({'active' if self.is_active else 'inactive'})"

    @property
    def unique_key(self) -> str:
        topic_part = self.topic or "global"
        return f"{topic_part}::{self.tray_id}"


class TrayEvent(models.Model):
    STATUS_ON = "on"
    STATUS_OFF = "off"
    STATUS_CHOICES = [
        (STATUS_ON, "On"),
        (STATUS_OFF, "Off"),
    ]

    tray = models.ForeignKey(
        TrayStatus, on_delete=models.CASCADE, related_name="events"
    )
    status = models.CharField(max_length=3, choices=STATUS_CHOICES)
    timestamp = models.DateTimeField()
    topic = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.tray.tray_id} {self.status} @ {self.timestamp.isoformat()}"
