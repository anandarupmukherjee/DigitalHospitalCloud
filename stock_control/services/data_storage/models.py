from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from django.utils.timezone import now
import uuid


def _today():
    return timezone.localdate()


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.name


class Location(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    SUPPLIER_CHOICES = [
        ('LEICA', 'Leica'),
        ('THIRD_PARTY', 'Third Party'),
    ]
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    product_code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    supplier = models.CharField(max_length=20, choices=SUPPLIER_CHOICES, default='LEICA')
    supplier_ref = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    threshold = models.PositiveIntegerField()
    lead_time = models.DurationField(default=timedelta(days=1), help_text="Lead time (e.g., 1 day, 2 hours)")

    def __str__(self):
        if self.product_code:
            return f"{self.product_code} - {self.name}"
        return self.name

    def available_items(self):
        return self.items.filter(expiry_date__gt=_today())

    def get_available_stock(self):
        return sum(
            (item.current_stock for item in self.available_items()),
            Decimal("0.00"),
        )

    def get_full_items_in_stock(self):
        return int(self.get_available_stock())

    def get_remaining_parts(self):
        return sum(item.accumulated_partial for item in self.available_items())

    @property
    def supplier_display(self):
        if self.supplier_ref:
            return self.supplier_ref.name
        return self.get_supplier_display()


class ProductItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="items")
    lot_number = models.CharField(max_length=50, default="LOT000")
    expiry_date = models.DateField(default=date.today)
    current_stock = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Stock available for this lot"
    )
    units_per_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('1.00'),
    )
    accumulated_partial = models.PositiveIntegerField(default=0)

    PRODUCT_FEATURE_CHOICES = [
        ('unit', 'Unit'),
        ('volume', 'Volume'),
    ]
    product_feature = models.CharField(max_length=10, choices=PRODUCT_FEATURE_CHOICES, default='volume')

    def __str__(self):
        return f"{self.product.name} (Lot {self.lot_number})"

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date <= _today())

    def get_full_items_in_stock(self):
        return 0 if self.is_expired else int(self.current_stock)

    def get_remaining_parts(self):
        return 0 if self.is_expired else self.accumulated_partial


class ProductIdentifier(models.Model):
    TYPE_INTERNAL_CODE = "INTERNAL_CODE"
    TYPE_GTIN = "GTIN"
    TYPE_SUPPLIER_CODE = "SUPPLIER_CODE"
    TYPE_NAME = "NAME"
    TYPE_SHORT_NAME = "SHORT_NAME"
    TYPE_LEGACY_CODE = "LEGACY_CODE"
    TYPE_OTHER = "OTHER"

    IDENTIFIER_TYPE_CHOICES = [
        (TYPE_INTERNAL_CODE, "Internal Code"),
        (TYPE_GTIN, "GTIN"),
        (TYPE_SUPPLIER_CODE, "Supplier Code"),
        (TYPE_NAME, "Name"),
        (TYPE_SHORT_NAME, "Short Name"),
        (TYPE_LEGACY_CODE, "Legacy Code"),
        (TYPE_OTHER, "Other"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="identifiers")
    identifier_type = models.CharField(max_length=32, choices=IDENTIFIER_TYPE_CHOICES)
    identifier_value = models.CharField(max_length=255)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    is_preferred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identifier_type", "identifier_value"],
                name="uniq_product_identifier_type_value",
            )
        ]
        indexes = [
            models.Index(fields=["identifier_type", "identifier_value"]),
        ]

    def __str__(self):
        return f"{self.identifier_type}:{self.identifier_value} -> {self.product_id}"

    def save(self, *args, **kwargs):
        self.identifier_value = (self.identifier_value or "").strip()
        self.identifier_type = (self.identifier_type or "").strip().upper()
        if self.supplier_name:
            self.supplier_name = self.supplier_name.strip()
        super().save(*args, **kwargs)


class ProductBarcodeAlias(models.Model):
    BARCODE_3PR = "3PR"
    BARCODE_GS1 = "GS1"
    BARCODE_GS1_BRACKETED = "GS1_BRACKETED"
    BARCODE_QR = "QR"
    BARCODE_UNKNOWN = "UNKNOWN"

    BARCODE_TYPE_CHOICES = [
        (BARCODE_3PR, "3PR"),
        (BARCODE_GS1, "GS1"),
        (BARCODE_GS1_BRACKETED, "GS1 Bracketed"),
        (BARCODE_QR, "QR"),
        (BARCODE_UNKNOWN, "Unknown"),
    ]

    TYPE_GTIN = "GTIN"
    TYPE_PARSED_PRODUCT_CODE = "PARSED_PRODUCT_CODE"
    TYPE_RAW_BARCODE = "RAW_BARCODE"
    TYPE_SUPPLIER_CODE = "SUPPLIER_CODE"
    TYPE_OTHER = "OTHER"

    IDENTIFIER_TYPE_CHOICES = [
        (TYPE_GTIN, "GTIN"),
        (TYPE_PARSED_PRODUCT_CODE, "Parsed Product Code"),
        (TYPE_RAW_BARCODE, "Raw Barcode"),
        (TYPE_SUPPLIER_CODE, "Supplier Code"),
        (TYPE_OTHER, "Other"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="barcode_aliases")
    barcode_type = models.CharField(max_length=32, choices=BARCODE_TYPE_CHOICES, default=BARCODE_UNKNOWN)
    identifier_type = models.CharField(max_length=32, choices=IDENTIFIER_TYPE_CHOICES)
    identifier_value = models.CharField(max_length=255)
    raw_barcode_sample = models.CharField(max_length=512, blank=True, null=True)
    supplier_name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identifier_type", "identifier_value"],
                name="uniq_barcode_alias_type_value",
            )
        ]
        indexes = [
            models.Index(fields=["identifier_type", "identifier_value"]),
            models.Index(fields=["barcode_type", "identifier_type"]),
        ]

    def __str__(self):
        return f"{self.identifier_type}:{self.identifier_value} -> {self.product_id}"

    def save(self, *args, **kwargs):
        self.identifier_value = (self.identifier_value or "").strip()
        self.identifier_type = (self.identifier_type or "").strip().upper()
        self.barcode_type = (self.barcode_type or self.BARCODE_UNKNOWN).strip().upper()
        if self.supplier_name:
            self.supplier_name = self.supplier_name.strip()
        if self.raw_barcode_sample:
            self.raw_barcode_sample = self.raw_barcode_sample.strip()
        super().save(*args, **kwargs)



class Withdrawal(models.Model):
    product_item = models.ForeignKey('ProductItem', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="For unit-based: store integer (e.g., 1.00); for volume-based: store decimal (e.g., 0.5)"
    )
    withdrawal_type = models.CharField(
        max_length=10,
        choices=[
            ('unit', 'Full Item'),
            ('volume', 'Volume'),
            ('part', 'Partial Withdrawal'),
            ('discarded', 'Lot Discarded'),
        ],
        default='unit'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawals",
    )
    barcode = models.CharField(max_length=128, blank=True, null=True)
    resolved_product_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    resolution_source = models.CharField(max_length=64, blank=True, null=True)

    parts_withdrawn = models.PositiveIntegerField(
        default=0,
        blank=True,
        help_text="Number of partial units withdrawn, if not a full item"
    )

    product_code = models.CharField(max_length=50, default="N/A")
    product_name = models.CharField(max_length=255, default="Unnamed Product")
    lot_number = models.CharField(max_length=50, default="UNKNOWN")
    expiry_date = models.DateField(default=date.today)

    def save(self, *args, **kwargs):
        if self.product_item:
            product = self.product_item.product
            self.product_code = product.product_code or "N/A"
            self.product_name = product.name
            self.lot_number = self.product_item.lot_number
            self.expiry_date = self.product_item.expiry_date
        super().save(*args, **kwargs)

    def get_full_items_withdrawn(self):
        return int(self.quantity)

    def get_partial_items_withdrawn(self):
        return self.parts_withdrawn

    def __str__(self):
        return f"{self.product_name} withdrawn on {self.timestamp}"


class StockRegistration(models.Model):
    product_item = models.ForeignKey('ProductItem', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_registrations",
    )
    barcode = models.CharField(max_length=128, blank=True, null=True)
    resolved_product_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    resolution_source = models.CharField(max_length=64, blank=True, null=True)

    product_code = models.CharField(max_length=50, default="N/A")
    product_name = models.CharField(max_length=255, default="Unnamed Product")
    lot_number = models.CharField(max_length=50, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.product_item:
            product = self.product_item.product
            self.product_code = product.product_code or "N/A"
            self.product_name = product.name
            self.lot_number = self.product_item.lot_number
            if not self.expiry_date:
                self.expiry_date = self.product_item.expiry_date
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} registered on {self.timestamp}"


class PurchaseOrder(models.Model):
    product_item = models.ForeignKey('ProductItem', on_delete=models.SET_NULL, null=True, blank=True)
    quantity_ordered = models.PositiveIntegerField(default=1)
    ordered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='Ordered')
    delivered_at = models.DateTimeField(null=True, blank=True)

    product_code = models.CharField(max_length=50, default="N/A")
    product_name = models.CharField(max_length=255, default="Unnamed Product")
    lot_number = models.CharField(max_length=50, default="UNKNOWN")
    expiry_date = models.DateField(default=date.today)

    def save(self, *args, **kwargs):
        if self.product_item:
            product = self.product_item.product
            self.product_code = product.product_code or "N/A"
            self.product_name = product.name
            self.lot_number = self.product_item.lot_number
            self.expiry_date = self.product_item.expiry_date
        super().save(*args, **kwargs)

    def mark_as_delivered(self):
        if self.status != 'Delivered' and self.product_item:
            self.product_item.quantity += self.quantity_ordered
            self.product_item.save()
            self.status = 'Delivered'
            self.save()

    def __str__(self):
        return f"PO-{self.id} for {self.product_name} (Lot {self.lot_number})"




class PurchaseOrderCompletionLog(models.Model):
    # Link to the original PO (optional, for traceability)
    purchase_order = models.ForeignKey(
        'PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='completion_logs'
    )

    # Snapshot fields (copied from related models at the time of completion)
    product_code = models.CharField(max_length=50)
    product_name = models.CharField(max_length=255)
    lot_number = models.CharField(max_length=50)
    expiry_date = models.DateField()

    quantity_ordered = models.PositiveIntegerField()
    ordered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='po_completions_created'
    )
    completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='po_completions_completed'
    )

    order_date = models.DateTimeField()
    completed_at = models.DateTimeField(default=now)

    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Completed PO - {self.product_name} ({self.product_code}) on {self.completed_at.strftime('%Y-%m-%d %H:%M')}"


class ProductDeletionArchive(models.Model):
    deleted_product_uuid = models.UUIDField(db_index=True)
    deleted_product_code = models.CharField(max_length=50, blank=True, default="")
    deleted_product_name = models.CharField(max_length=255)
    supplier = models.CharField(max_length=100, blank=True, default="")
    location_name = models.CharField(max_length=100, blank=True, default="")
    threshold = models.PositiveIntegerField(default=0)
    lead_time_seconds = models.BigIntegerField(default=0)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_product_archives",
    )
    deleted_at = models.DateTimeField(default=timezone.now, db_index=True)
    items_snapshot = models.JSONField(default=list, blank=True)
    identifiers_snapshot = models.JSONField(default=list, blank=True)
    barcode_aliases_snapshot = models.JSONField(default=list, blank=True)

    def __str__(self):
        code = self.deleted_product_code or "NO-CODE"
        return f"Deleted Product {code} - {self.deleted_product_name}"
