from django.conf import settings
from django.db import models

from services.data_storage.models import ProductItem


class QualityCheck(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
    ]

    RESULT_CHOICES = [
        ("pass", "Pass"),
        ("fail", "Fail"),
    ]

    product_item = models.ForeignKey(
        ProductItem,
        on_delete=models.CASCADE,
        related_name="quality_checks",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_checks_performed",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    test_reference = models.CharField(max_length=120, blank=True)
    result = models.CharField(max_length=4, choices=RESULT_CHOICES, blank=True)
    signed_off_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_checks_signed",
    )
    signed_off_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"QC {self.product_item} - {self.test_reference or 'N/A'}"
