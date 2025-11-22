from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Prefetch
from django.shortcuts import redirect, render
from django.utils import timezone

from inventory.access_control import group_required
from inventory.roles import ROLE_INVENTORY_MANAGER
from services.data_collection.data_collection import parse_barcode_data
from services.data_storage.models import Product, ProductItem

from .forms import QualityCheckForm
from .models import QualityCheck

User = get_user_model()


def is_inventory_admin(user):
    return user.is_authenticated and (user.is_superuser or user.groups.filter(name=ROLE_INVENTORY_MANAGER).exists())


@login_required
@group_required([ROLE_INVENTORY_MANAGER])
def list_checks(request):
    checks = (
        QualityCheck.objects.select_related(
            "product_item",
            "product_item__product",
            "performed_by",
            "signed_off_by",
        )
        .order_by("-created_at")
    )
    return render(
        request,
        "quality_control/list_checks.html",
        {"checks": checks},
    )


@login_required
@group_required([ROLE_INVENTORY_MANAGER])
def lot_status(request):
    """Show lots for a selected/scanned product with latest QC status."""
    raw_messages = messages.get_messages(request)
    qc_messages = [m for m in raw_messages if m.level_tag in ("error", "warning")]

    products = (
        Product.objects.filter(items__current_stock__gt=0)
        .order_by("name")
        .distinct()
    )
    selected_product = None

    barcode_value = (request.GET.get("barcode") or "").strip()
    product_id = request.GET.get("product_id")

    if barcode_value:
        parsed = parse_barcode_data(barcode_value)
        product_code = ""
        if parsed:
            product_code = (parsed.get("product_code") or "").strip()
        else:
            product_code = barcode_value

        lookup_codes = [product_code, barcode_value]
        if product_code.isdigit():
            lookup_codes.append(product_code.lstrip("0"))

        for code in lookup_codes:
            if not code:
                continue
            selected_product = Product.objects.filter(product_code__iexact=code).first()
            if selected_product:
                break
        if not selected_product:
            messages.error(request, "No product matches the scanned barcode.")

    if not selected_product and product_id:
        selected_product = Product.objects.filter(pk=product_id).first()
        if not selected_product:
            messages.error(request, "Selected product not found.")

    lot_status_rows = []
    if selected_product:
        items = (
            ProductItem.objects.filter(product=selected_product)
            .select_related("product")
            .prefetch_related(
                Prefetch("quality_checks", queryset=QualityCheck.objects.order_by("-created_at"))
            )
            .order_by("lot_number", "expiry_date")
        )

        # Build a map of location stock per item (if location tracking enabled)
        location_stock_map = {}
        try:
            from solutions.location_tracking.models import LocationStock

            loc_rows = LocationStock.objects.filter(product_item__product=selected_product).values(
                "product_item_id"
            ).annotate(total=Sum("quantity"))
            for row in loc_rows:
                location_stock_map[row["product_item_id"]] = row["total"]
        except Exception:
            pass

        for item in items:
            location_qty = Decimal(location_stock_map.get(item.id, 0) or 0)
            total_effective = Decimal(item.current_stock) + location_qty
            if total_effective <= 0:
                continue

            checks = list(item.quality_checks.all())
            latest_check = checks[0] if checks else None
            if latest_check and latest_check.result == "pass":
                status_label = "Pass"
                status_class = "qc-pass"
            elif latest_check and latest_check.result == "fail":
                status_label = "Fail"
                status_class = "qc-fail"
            elif latest_check:
                status_label = "Pending"
                status_class = "qc-pending"
            else:
                status_label = "Waiting for QC"
                status_class = "qc-pending"

            lot_status_rows.append(
                {
                    "item": item,
                    "latest_check": latest_check,
                    "status_label": status_label,
                    "status_class": status_class,
                    "total_effective": total_effective,
                }
            )

    return render(
        request,
        "quality_control/lot_status.html",
        {
            "products": products,
            "selected_product": selected_product,
            "lot_status_rows": lot_status_rows,
            "barcode_value": barcode_value,
            "qc_messages": qc_messages,
        },
    )


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def create_check(request):
    if request.method == "POST":
        form = QualityCheckForm(request.POST)
        if form.is_valid():
            qc = form.save(commit=False)
            qc.performed_by = request.user
            if qc.result or qc.status == QualityCheck.STATUS_COMPLETED:
                qc.status = QualityCheck.STATUS_COMPLETED
                qc.signed_off_by = request.user
                qc.signed_off_at = timezone.now()
            qc.save()
            return redirect("quality_control:list_checks")
    else:
        form = QualityCheckForm()
    return render(
        request,
        "quality_control/create_check.html",
        {"form": form},
    )
