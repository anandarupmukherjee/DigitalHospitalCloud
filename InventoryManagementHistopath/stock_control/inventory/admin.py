from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from services.data_storage.models import (
    Product,
    ProductItem,
    Withdrawal,
    PurchaseOrder,
    Supplier,
    Location,
)

# ✅ Custom UserAdmin
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

# ✅ Unregister default User and re-register with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "contact_phone")
    search_fields = ("name",)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_code", "name", "supplier", "threshold", "lead_time")
    search_fields = ("product_code", "name")
    raw_id_fields = ("supplier_ref", "location")


@admin.register(ProductItem)
class ProductItemAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "lot_number",
        "expiry_date",
        "current_stock",
        "product_feature"
    )
    list_filter = ("product__supplier", "product_feature", "expiry_date")
    search_fields = ("product__name", "lot_number")


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = (
        "product_item",
        "product_code",
        "quantity",
        "withdrawal_type",
        "timestamp",
        "user"
    )
    list_filter = ("withdrawal_type", "timestamp")
    search_fields = ("product_code", "product_name", "lot_number", "user__username")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "product_item",
        "product_code",
        "quantity_ordered",
        "order_date",
        "expected_delivery",
        "status"
    )
    list_filter = ("status", "expected_delivery")
    search_fields = ("product_code", "product_name", "lot_number")
