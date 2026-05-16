import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, render

from inventory.access_control import group_required
from inventory.roles import ROLE_INVENTORY_MANAGER, ROLE_TEAM_MANAGER
from inventory.location_utils import (
    ACTIVE_USER_LOCATION_SESSION_KEY,
    build_user_location_state,
    coerce_location_id,
)
from services.data_collection.data_collection import parse_barcode_data
from services.data_collection.barcode_resolution import parse_expiry_date, resolve_product_from_barcode
from services.data_storage.models import Product, ProductItem, StockRegistration


def _find_product_by_ref(ref):
    value = (ref or "").strip()
    if not value:
        return None
    if value.isdigit():
        return Product.objects.filter(id=int(value)).first()
    return Product.objects.filter(uuid=value).first()


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_TEAM_MANAGER])
def register_stock(request):
    location_state = build_user_location_state(
        request.user, request.session.get(ACTIVE_USER_LOCATION_SESSION_KEY)
    )
    location_choices = location_state["locations"]
    allowed_location_ids = location_state["allowed_ids"]
    location_selection_required = location_state["selection_required"]
    selected_location_id = location_state["selected_id"]

    recent_registrations = (
        StockRegistration.objects.select_related("product_item", "user", "location")
        .order_by("-timestamp")[:10]
    )
    register_messages = [m for m in messages.get_messages(request) if "register_stock" in m.tags]

    if request.method == "POST":
        raw_barcode = (request.POST.get("barcode") or "").strip()
        posted_location_id = coerce_location_id(request.POST.get("selected_location"))
        if posted_location_id is not None:
            selected_location_id = posted_location_id
        location_error = None
        if allowed_location_ids:
            if location_selection_required and not selected_location_id:
                location_error = "Select a location before registering stock."
            elif selected_location_id and selected_location_id not in allowed_location_ids:
                location_error = "Invalid location selected."
                selected_location_id = None
        else:
            selected_location_id = None

        if location_error:
            messages.error(request, location_error, extra_tags="register_stock")
            return redirect("data_collection_3:register_stock")

        if not raw_barcode:
            messages.error(request, "Scan a barcode to register stock.", extra_tags="register_stock")
            return redirect("data_collection_3:register_stock")

        parsed = parse_barcode_data(raw_barcode) or {}
        resolution = resolve_product_from_barcode(parsed, raw_barcode)
        product = resolution["product"]
        lot_number = (parsed.get("lot_number") or "").strip()
        expiry_date = parse_expiry_date((parsed.get("expiry_date") or "").strip())

        if not product:
            selected_uuid = (request.POST.get("resolved_product_uuid") or "").strip()
            if selected_uuid:
                product = _find_product_by_ref(selected_uuid)
                if product:
                    resolution["source"] = "frontend_resolved_uuid"
                if product and not lot_number:
                    lot_number = (request.POST.get("lot_number") or "").strip()
                if product and not expiry_date:
                    expiry_date = parse_expiry_date((request.POST.get("expiry_date") or "").strip())

        if not product:
            messages.error(request, "No product matches the scanned barcode.", extra_tags="register_stock")
            return redirect("data_collection_3:register_stock")

        item_qs = product.items.all()
        if lot_number:
            item_qs = item_qs.filter(lot_number__iexact=lot_number)
        if expiry_date:
            item_qs = item_qs.filter(expiry_date=expiry_date)

        item = item_qs.order_by("-expiry_date").first()
        created_new_item = False

        with transaction.atomic():
            if not item:
                # Auto-create a product item/lot when the scanned details are new.
                item = ProductItem.objects.create(
                    product=product,
                    lot_number=lot_number or "LOT000",
                    expiry_date=expiry_date or datetime.date.today(),
                )
                created_new_item = True

            item.current_stock = F("current_stock") + 1
            item.save(update_fields=["current_stock"])
            item.refresh_from_db(fields=["current_stock"])

            StockRegistration.objects.create(
                product_item=item,
                quantity=1,
                user=request.user,
                location_id=selected_location_id,
                barcode=raw_barcode,
                resolved_product_uuid=product.uuid,
                resolution_source=resolution.get("source"),
                lot_number=lot_number or item.lot_number,
                expiry_date=expiry_date or item.expiry_date,
            )

        if selected_location_id:
            request.session[ACTIVE_USER_LOCATION_SESSION_KEY] = selected_location_id

        if item.is_expired:
            messages.error(
                request,
                "Lot has expired.",
                extra_tags="register_stock expired_lot",
            )

        if created_new_item:
            messages.info(
                request,
                f"Created new lot {item.lot_number} for {product.name}.",
                extra_tags="register_stock",
            )

        messages.success(
            request,
            f"Registered stock for {item.product.name} (Lot {item.lot_number}). Current stock: {item.current_stock}.",
            extra_tags="register_stock",
        )
        return redirect("data_collection_3:register_stock")

    return render(
        request,
        "inventory/register_stock.html",
        {
            "recent_registrations": recent_registrations,
            "register_messages": register_messages,
            "location_choices": location_choices,
            "location_selection_required": location_selection_required,
            "selected_location_id": selected_location_id,
        },
    )
