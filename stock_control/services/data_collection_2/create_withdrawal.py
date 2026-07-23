import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django.contrib import messages
from django.db.models import F
from django.shortcuts import redirect, render
from django.utils import timezone

from inventory.forms import WithdrawalForm
from inventory.location_utils import (
    ACTIVE_USER_LOCATION_SESSION_KEY,
    build_user_location_state,
    coerce_location_id,
)
from services.data_collection.data_collection import parse_barcode_data
from services.data_collection.barcode_resolution import parse_expiry_date, resolve_product_from_barcode
from services.data_storage.models import Product, ProductItem, Withdrawal


def _find_product_by_ref(ref):
    value = (ref or "").strip()
    if not value:
        return None
    if value.isdigit():
        return Product.objects.filter(id=int(value)).first()
    return Product.objects.filter(uuid=value).first()


def create_withdrawal(request):
    location_state = build_user_location_state(
        request.user, request.session.get(ACTIVE_USER_LOCATION_SESSION_KEY)
    )
    location_choices = location_state["locations"]
    allowed_location_ids = location_state["allowed_ids"]
    location_selection_required = location_state["selection_required"]
    selected_location_id = location_state["selected_id"]

    def fmt_decimal(value):
        if value is None:
            return "0"
        normalized = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        text = format(normalized, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    def render_form(current_form):
        products = Product.objects.filter(
            items__current_stock__gt=0,
            items__expiry_date__gt=timezone.localdate(),
        ).distinct().order_by("name")
        return render(
            request,
            'inventory/create_withdrawal.html',
            {
                'form': current_form,
                'products': products,
                'location_choices': location_choices,
                'location_selection_required': location_selection_required,
                'selected_location_id': selected_location_id,
            },
        )

    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        posted_location_id = coerce_location_id(request.POST.get("selected_location"))
        if posted_location_id is not None:
            selected_location_id = posted_location_id
        location_error = None
        if allowed_location_ids:
            if location_selection_required and not selected_location_id:
                location_error = "Select a location for this withdrawal."
            elif selected_location_id and selected_location_id not in allowed_location_ids:
                location_error = "Invalid location selected."
                selected_location_id = None
        else:
            selected_location_id = None
        if form.is_valid() and not location_error:
            withdrawal = form.save(commit=False)
            withdrawal.user = request.user

            # ✅ Parse relevant fields
            raw_barcode = (form.cleaned_data.get("barcode") or "").strip()
            barcode = raw_barcode or (request.POST.get("barcode_manual") or "").strip()
            product_dropdown = request.POST.get("product_dropdown")
            manual_lot_item_id = (request.POST.get("manual_lot_item_id") or "").strip()
            barcode_mode = not bool(product_dropdown)
            resolved_product_uuid = (request.POST.get("resolved_product_uuid") or "").strip()
            lot_number = (request.POST.get("lot_number") or "").strip()
            expiry_date_raw = (request.POST.get("expiry_date") or "").strip()

            print("🔍 DEBUG Withdrawal:")
            print("Product code:", barcode)
            print("Lot:", lot_number)
            print("Expiry (raw):", expiry_date_raw)
            print("Dropdown:", product_dropdown)

            # ✅ Lookup product item
            item = None
            resolution_source = "manual_dropdown"
            if product_dropdown:
                product = Product.objects.filter(id=product_dropdown).first()
                item_qs = ProductItem.objects.filter(
                    product=product,
                    current_stock__gt=0,
                    expiry_date__gt=timezone.localdate(),
                )
                if manual_lot_item_id:
                    item = item_qs.filter(id=manual_lot_item_id).first()
                else:
                    item = item_qs.order_by('-expiry_date').first()
            else:
                parsed = parse_barcode_data(raw_barcode) if raw_barcode else None
                resolution = resolve_product_from_barcode(parsed, raw_barcode)
                product = resolution["product"]
                resolution_source = resolution.get("source")
                if not product and resolved_product_uuid:
                    product = _find_product_by_ref(resolved_product_uuid)
                    if product:
                        resolution_source = "frontend_resolved_uuid"

                expiry_date_obj = parse_expiry_date(expiry_date_raw)
                if product:
                    item_qs = ProductItem.objects.filter(product=product)
                    if lot_number:
                        item_qs = item_qs.filter(lot_number__iexact=lot_number.strip())
                    if expiry_date_obj:
                        item_qs = item_qs.filter(expiry_date=expiry_date_obj)
                    item = item_qs.first()


            if product_dropdown and manual_lot_item_id and not item:
                form.add_error(None, "Select a valid lot for manual withdrawal.")
                return render_form(form)

            if item:
                withdrawal.product_item = item
                withdrawal.barcode = barcode
                withdrawal.resolved_product_uuid = item.product.uuid
                withdrawal.resolution_source = resolution_source
                if selected_location_id:
                    withdrawal.location_id = selected_location_id

                partial_only_item = item.product_feature == 'volume' or item.units_per_quantity > 1

                if item.product_feature == 'volume':
                    # Volume reagents are withdrawn by an actual amount (mL),
                    # fractions allowed. A barcode scan removes one dose
                    # (units_per_quantity); manual entry uses the typed amount.
                    if barcode_mode:
                        volume_qty = Decimal(item.units_per_quantity or 0)
                        if volume_qty <= 0:
                            volume_qty = Decimal("1")
                    else:
                        raw_volume = request.POST.get("volume_quantity")
                        if raw_volume in (None, ""):
                            raw_volume = form.cleaned_data.get("quantity")
                        try:
                            volume_qty = Decimal(str(raw_volume or "0"))
                        except (InvalidOperation, TypeError):
                            volume_qty = Decimal("0")
                    if volume_qty <= 0:
                        form.add_error(None, "Enter a volume greater than 0 (mL) to withdraw.")
                        return render_form(form)
                    if volume_qty > item.current_stock:
                        form.add_error(None, "Insufficient stock for this volume withdrawal.")
                        return render_form(form)
                    withdrawal.quantity = volume_qty
                    withdrawal.parts_withdrawn = 0
                    withdrawal.withdrawal_type = 'volume'
                    item.current_stock = F('current_stock') - volume_qty

                else:
                    withdrawal_mode = "part" if (barcode_mode and item.units_per_quantity > 1) or (not barcode_mode and partial_only_item) else "full"

                    if withdrawal_mode == "part":
                        if barcode_mode:
                            parts_withdrawn = 1
                        else:
                            try:
                                parts_withdrawn = int(Decimal(str(request.POST.get("parts_withdrawn") or "0")))
                            except (InvalidOperation, TypeError, ValueError):
                                parts_withdrawn = 0
                        if parts_withdrawn <= 0:
                            form.add_error(None, "Enter at least 1 part to withdraw.")
                            return render_form(form)
                        units_per_item = item.units_per_quantity
                        current_partial = item.accumulated_partial
                        total_units = current_partial + parts_withdrawn

                        full_items = total_units // units_per_item
                        remaining_partial = total_units % units_per_item

                        if full_items > 0:
                            if full_items > item.current_stock:
                                form.add_error(None, "Insufficient stock for partial withdrawal conversion.")
                                return render_form(form)
                            item.current_stock = F('current_stock') - full_items
                        item.accumulated_partial = remaining_partial

                        withdrawal.quantity = full_items
                        withdrawal.parts_withdrawn = parts_withdrawn
                        withdrawal.withdrawal_type = 'part'

                    else:
                        if barcode_mode:
                            full_items = Decimal("1")
                        else:
                            try:
                                full_items = Decimal(str(form.cleaned_data.get("quantity") or "0"))
                            except (InvalidOperation, TypeError):
                                full_items = Decimal("0")
                        if full_items <= 0:
                            form.add_error(None, "Enter at least 1 item to withdraw.")
                            return render_form(form)
                        if full_items != full_items.to_integral_value():
                            form.add_error(None, "Full item withdrawal must be a whole number.")
                            return render_form(form)
                        if full_items > item.current_stock:
                            form.add_error(None, "Insufficient stock for full withdrawal.")
                            return render_form(form)
                        withdrawal.quantity = full_items
                        withdrawal.parts_withdrawn = 0
                        withdrawal.withdrawal_type = 'unit'
                        item.current_stock = F('current_stock') - full_items

                item.save()
                item.refresh_from_db()
                withdrawal.save()
                if selected_location_id:
                    request.session[ACTIVE_USER_LOCATION_SESSION_KEY] = selected_location_id
                if item.product_feature == 'volume' and (barcode_mode or withdrawal.withdrawal_type == 'part'):
                    success_message = f"{fmt_decimal(withdrawal.quantity)} mL withdrawn from {item.product.name} (Lot {item.lot_number})."
                else:
                    success_message = f"Withdrawal successful for {item.product.name} (Lot {item.lot_number})."
                messages.success(
                    request,
                    success_message,
                    extra_tags="withdrawal_success",
                )
                return redirect('data_collection_2:create_withdrawal')
            else:
                form.add_error(None, "Product item not found. Check barcode, lot number, or expiry date.")
        else:
            if location_error:
                form.add_error(None, location_error)
            else:
                print("❌ Form Errors:", form.errors)

    else:
        form = WithdrawalForm()

    return render_form(form)
