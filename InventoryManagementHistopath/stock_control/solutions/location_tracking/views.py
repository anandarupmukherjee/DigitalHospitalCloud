from collections import defaultdict
import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from inventory.access_control import group_required
from inventory.roles import ROLE_INVENTORY_MANAGER, user_is_inventory_manager
from services.data_collection.data_collection import parse_barcode_data
from services.data_storage.models import Location, Product, ProductItem

from .forms import LocationStockForm, LocationTransferForm, UserLocationForm
from .models import LocationStock, UserLocation, adjust_location_stock


def is_inventory_admin(user):
    return user_is_inventory_manager(user)


def _resolve_product_item_from_barcode(raw):
    barcode_data = parse_barcode_data(raw)
    if not barcode_data:
        return None
    raw_code = barcode_data.get("product_code") or ""
    normalized_code = barcode_data.get("normalized_product_code") or ""
    product_code_candidates = []
    for value in [raw_code, normalized_code]:
        if not value:
            continue
        if value not in product_code_candidates:
            product_code_candidates.append(value)
        stripped = value.lstrip("0")
        if stripped and stripped != value and stripped not in product_code_candidates:
            product_code_candidates.append(stripped)

    lot_number = barcode_data.get("lot_number")
    expiry_str = barcode_data.get("expiry_date")

    product = None
    for candidate in product_code_candidates:
        product = Product.objects.filter(product_code__iexact=candidate).first()
        if product:
            break
    if not product:
        return None

    item_qs = ProductItem.objects.filter(product=product)
    if lot_number:
        item_qs = item_qs.filter(lot_number__iexact=lot_number)
    if expiry_str:
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.datetime.strptime(expiry_str, fmt).date()
                item_qs = item_qs.filter(expiry_date=parsed)
                break
            except ValueError:
                continue
    return item_qs.order_by("expiry_date").first()


def _resolve_product_item_from_ids(product_id, item_id):
    if not (product_id and item_id):
        return None
    return ProductItem.objects.filter(product_id=product_id, id=item_id).select_related("product").first()


def _get_location_stock(location_id, product_item):
    if not (location_id and product_item):
        return None
    try:
        stock = LocationStock.objects.get(location_id=location_id, product_item=product_item)
        return stock.quantity
    except LocationStock.DoesNotExist:
        return Decimal("0")


@login_required
@group_required([ROLE_INVENTORY_MANAGER])
def overview(request):
    stocks = (
        LocationStock.objects.select_related("location", "product_item", "product_item__product")
        .order_by("location__name", "product_item__product__name")
    )
    filter_location_id = request.GET.get("location")
    if filter_location_id:
        stocks = stocks.filter(location_id=filter_location_id)

    location_totals = defaultdict(Decimal)
    for stock in stocks:
        location_totals[stock.location_id] += stock.quantity
    locations = Location.objects.order_by("name")
    location_summary = [
        {"location": location, "total": location_totals.get(location.id, Decimal("0.00"))}
        for location in locations
    ]
    return render(
        request,
        "location_tracking/overview.html",
        {
            "location_summary": location_summary,
            "stocks": stocks,
        },
    )


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def add_stock(request):
    initial = {}
    barcode_prefill = request.GET.get("barcode_lookup", "").strip()
    selected_item = None
    location_balances = []
    display_total_stock = None
    if barcode_prefill:
        resolved_item = _resolve_product_item_from_barcode(barcode_prefill)
        if resolved_item:
            initial["product"] = str(resolved_item.product_id)
            initial["product_item"] = str(resolved_item.id)
            selected_item = resolved_item
        else:
            messages.error(request, "Could not identify product/lot from barcode.")

    location_stock_quantity = None
    selected_location_id = None

    if request.method == "POST":
        form = LocationStockForm(request.POST)
        if form.is_valid():
            product_item = form.cleaned_data["product_item"]
            location = form.cleaned_data["location"]
            quantity = form.cleaned_data["quantity"]
            adjust_location_stock(location, product_item, quantity)
            product_item.current_stock += quantity
            product_item.save(update_fields=["current_stock"])
            messages.success(request, "Stock added to location.")
            return redirect("location_tracking:overview")
        else:
            if not selected_item:
                selected_item = _resolve_product_item_from_ids(form.data.get("product"), form.data.get("product_item"))
            selected_location_id = form.data.get("location")
    else:
        form = LocationStockForm(initial=initial)
        if not selected_item:
            selected_item = _resolve_product_item_from_ids(initial.get("product"), initial.get("product_item"))

    if not selected_location_id:
        selected_location_id = form.data.get("location") if form.is_bound else form.initial.get("location")

    if selected_location_id and selected_item:
        location_stock_quantity = _get_location_stock(selected_location_id, selected_item)

    if selected_item:
        stock_rows = (
            LocationStock.objects.select_related("location")
            .filter(product_item=selected_item)
            .order_by("location__name")
        )
        loc_map = {row.location_id: row.quantity for row in stock_rows}
        if selected_item.product.location_id and selected_item.product.location_id not in loc_map:
            loc_map[selected_item.product.location_id] = Decimal("0.00")
        location_ids = list(loc_map.keys())
        locations = Location.objects.filter(id__in=location_ids).order_by("name")
        location_balances = [
            {"location": loc, "quantity": loc_map.get(loc.id, Decimal("0.00"))} for loc in locations
        ]
        if loc_map:
            display_total_stock = sum(loc_map.values())
        else:
            display_total_stock = selected_item.current_stock

    return render(
        request,
        "location_tracking/add_stock.html",
        {
            "form": form,
            "barcode_lookup_value": barcode_prefill,
            "selected_item": selected_item,
            "location_stock_quantity": location_stock_quantity,
            "location_balances": location_balances,
            "display_total_stock": display_total_stock,
        },
    )


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def transfer_stock(request):
    initial = {}
    barcode_prefill = request.GET.get("barcode_lookup", "").strip()
    selected_item = None
    location_balances = []
    if barcode_prefill:
        resolved_item = _resolve_product_item_from_barcode(barcode_prefill)
        if resolved_item:
            initial["product"] = str(resolved_item.product_id)
            initial["product_item"] = str(resolved_item.id)
            selected_item = resolved_item
        else:
            messages.error(request, "Could not identify product/lot from barcode.")

    selected_from_location_id = None
    initial_stock_quantity = None

    if request.method == "POST":
        form = LocationTransferForm(request.POST)
        if form.is_valid():
            product_item = form.cleaned_data["product_item"]
            from_location = form.cleaned_data["from_location"]
            to_location = form.cleaned_data["to_location"]
            quantity = form.cleaned_data["quantity"]
            try:
                adjust_location_stock(from_location, product_item, -quantity)
                adjust_location_stock(to_location, product_item, quantity)
            except ValueError:
                form.add_error(None, "Insufficient stock at source location.")
            else:
                messages.success(request, "Stock transferred successfully.")
                return redirect("location_tracking:overview")
        if not selected_item:
            selected_item = _resolve_product_item_from_ids(form.data.get("product"), form.data.get("product_item"))
        selected_from_location_id = form.data.get("from_location")
    else:
        form = LocationTransferForm(initial=initial)
        if not selected_item:
            selected_item = _resolve_product_item_from_ids(initial.get("product"), initial.get("product_item"))
        if form.is_bound:
            selected_from_location_id = form.data.get("from_location")
        else:
            selected_from_location_id = form.initial.get("from_location")

    if selected_from_location_id and selected_item:
        initial_stock_quantity = _get_location_stock(selected_from_location_id, selected_item)

    # Build per-location balances for the selected item
    if selected_item:
        stock_rows = (
            LocationStock.objects.select_related("location")
            .filter(product_item=selected_item)
            .order_by("location__name")
        )
        loc_map = {row.location_id: row.quantity for row in stock_rows}
        # Ensure the product's default location shows up even if no stock record
        if selected_item.product.location_id and selected_item.product.location_id not in loc_map:
            loc_map[selected_item.product.location_id] = Decimal("0.00")

        location_ids = list(loc_map.keys())
        locations = Location.objects.filter(id__in=location_ids).order_by("name")
        location_balances = [
            {"location": loc, "quantity": loc_map.get(loc.id, Decimal("0.00"))} for loc in locations
        ]

    return render(
        request,
        "location_tracking/transfer_stock.html",
        {
            "form": form,
            "barcode_lookup_value": barcode_prefill,
            "selected_item": selected_item,
            "initial_stock_quantity": initial_stock_quantity,
            "location_balances": location_balances,
        },
    )


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def manage_user_locations(request):
    if request.method == "POST":
        form = UserLocationForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data["user"]
            locations = form.cleaned_data["locations"]
            UserLocation.objects.filter(user=user).delete()
            UserLocation.objects.bulk_create(
                [UserLocation(user=user, location=location) for location in locations]
            )
            messages.success(request, "User locations updated.")
            return redirect(f"{request.path}?user={user.pk}")
    else:
        initial = {}
        selected_user_id = request.GET.get("user")
        if selected_user_id:
            selected_locations = UserLocation.objects.filter(user_id=selected_user_id).values_list("location_id", flat=True)
            initial = {"user": selected_user_id, "locations": list(selected_locations)}
        form = UserLocationForm(initial=initial)
    selected_user = form.initial.get("user")
    assignments = UserLocation.objects.select_related("location").filter(user_id=selected_user) if selected_user else []
    return render(
        request,
        "location_tracking/user_locations.html",
        {"form": form, "assignments": assignments},
    )


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def location_stock_snapshot(request):
    product_item_id = request.GET.get("product_item")
    location_id = request.GET.get("location")
    if not (product_item_id and location_id):
        return JsonResponse({"error": "Missing product_item or location"}, status=400)

    try:
        product_item = ProductItem.objects.select_related("product").get(id=product_item_id)
    except ProductItem.DoesNotExist:
        return JsonResponse({"error": "Product item not found"}, status=404)

    try:
        location_id_int = int(location_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid location id"}, status=400)

    quantity = _get_location_stock(location_id_int, product_item)
    return JsonResponse(
        {
            "current_stock": str(quantity),
            "threshold": product_item.product.threshold,
        }
    )
