import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import redirect, render

from inventory.access_control import group_required
from services.data_collection.data_collection import parse_barcode_data
from services.data_storage.models import Product, StockRegistration
from services.data_storage.models import ProductItem


@login_required
@group_required(["Inventory Manager"])
def register_stock(request):
    recent_registrations = StockRegistration.objects.select_related("product_item", "user").order_by("-timestamp")[:10]
    register_messages = [m for m in messages.get_messages(request) if "register_stock" in m.tags]

    if request.method == "POST":
        raw_barcode = (request.POST.get("barcode") or "").strip()

        if not raw_barcode:
            messages.error(request, "Scan a barcode to register stock.", extra_tags="register_stock")
            return redirect("data_collection_3:register_stock")

        parsed = parse_barcode_data(raw_barcode)
        product_code = ""
        lot_number = ""
        expiry_str = ""

        if parsed:
            product_code = (parsed.get("product_code") or "").strip()
            lot_number = (parsed.get("lot_number") or "").strip()
            expiry_str = (parsed.get("expiry_date") or "").strip()
        else:
            product_code = raw_barcode

        expiry_date = None
        if expiry_str:
            for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                try:
                    expiry_date = datetime.datetime.strptime(expiry_str, fmt).date()
                    break
                except ValueError:
                    continue

        search_codes = []
        candidates = [product_code, raw_barcode]
        for code in candidates:
            if not code:
                continue
            search_codes.append(code)
            if code.isdigit():
                search_codes.append(code.lstrip("0"))

        product = None
        for code in search_codes:
            if not code:
                continue
            product = Product.objects.filter(product_code__iexact=code).first()
            if product:
                break

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
                barcode=raw_barcode,
                lot_number=lot_number or item.lot_number,
                expiry_date=expiry_date or item.expiry_date,
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
        },
    )
