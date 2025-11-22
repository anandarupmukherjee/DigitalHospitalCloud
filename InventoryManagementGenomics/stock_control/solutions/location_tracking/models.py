from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

from services.data_storage.models import Location, ProductItem


class LocationStock(models.Model):
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="location_stocks",
    )
    product_item = models.ForeignKey(
        ProductItem,
        on_delete=models.CASCADE,
        related_name="location_stocks",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("location", "product_item")

    def __str__(self):
        return f"{self.product_item} @ {self.location} ({self.quantity})"


class UserLocation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_assignments",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="user_assignments",
    )

    class Meta:
        unique_together = ("user", "location")

    def __str__(self):
        return f"{self.user} -> {self.location}"


def adjust_location_stock(location, product_item, delta):
    with transaction.atomic():
        stock, _ = LocationStock.objects.select_for_update().get_or_create(
            location=location,
            product_item=product_item,
            defaults={"quantity": Decimal("0.00")},
        )
        stock.quantity = stock.quantity + Decimal(delta)
        if stock.quantity < 0:
            raise ValueError("Insufficient stock at location.")
        stock.save(update_fields=["quantity", "updated_at"])
        return stock
