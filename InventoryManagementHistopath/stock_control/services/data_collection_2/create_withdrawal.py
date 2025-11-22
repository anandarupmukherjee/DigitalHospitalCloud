from django.shortcuts import render, redirect
from django.db.models import F
import datetime

from services.data_storage.models import Product, ProductItem, Withdrawal
from inventory.forms import WithdrawalForm
from services.data_collection.data_collection import parse_barcode_data


def _candidate_codes(*values):
    seen = []
    for value in values:
        if not value:
            continue
        if value not in seen:
            seen.append(value)
        stripped = value.lstrip("0")
        if stripped and stripped != value and stripped not in seen:
            seen.append(stripped)
    return seen


def create_withdrawal(request):
    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            withdrawal = form.save(commit=False)
            withdrawal.user = request.user

            # ✅ Parse relevant fields
            barcode = (
                request.POST.get("product_code_from_barcode") or
                form.cleaned_data.get("barcode") or
                request.POST.get("barcode_manual")
            )
            product_dropdown = request.POST.get("product_dropdown")
            lot_number = (request.POST.get("lot_number") or "").strip()
            expiry_date_raw = (request.POST.get("expiry_date") or "").strip()

            print("🔍 DEBUG Withdrawal:")
            print("Product code:", barcode)
            print("Lot:", lot_number)
            print("Expiry (raw):", expiry_date_raw)
            print("Dropdown:", product_dropdown)

            # ✅ Lookup product item
            item = None
            if product_dropdown:
                product = Product.objects.filter(id=product_dropdown).first()
                item = (
                    ProductItem.objects.filter(product=product, current_stock__gt=0)
                    .order_by('-expiry_date')
                    .first()
                )
            else:
                # Validate lot_number and expiry_date before querying
                # Normalize barcode
                barcode_data = parse_barcode_data(barcode) if barcode else None
                code_candidates = _candidate_codes(
                    request.POST.get("product_code_from_barcode"),
                    barcode_data.get("raw_product_code") if barcode_data else None,
                    barcode_data.get("product_code") if barcode_data else None,
                    barcode_data.get("normalized_product_code") if barcode_data else None,
                    barcode,
                )

                # Start with matching product
                product = None
                for candidate in code_candidates or []:
                    product = Product.objects.filter(product_code__iexact=candidate).first()
                    if product:
                        break

                expiry_date_obj = None
                if expiry_date_raw:
                    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                        try:
                            expiry_date_obj = datetime.datetime.strptime(expiry_date_raw, fmt).date()
                            break
                        except ValueError:
                            continue

                if expiry_date_obj:
                    print("Expiry (parsed):", expiry_date_obj)

                if product:
                    item_qs = ProductItem.objects.filter(product=product)

                    if lot_number:
                        item_qs = item_qs.filter(lot_number__iexact=lot_number.strip())

                    if expiry_date_obj:
                        item_qs = item_qs.filter(expiry_date=expiry_date_obj)

                    item = item_qs.first()


            if item:
                withdrawal.product_item = item
                withdrawal.barcode = barcode

                if item.product_feature == 'volume':
                    volume_qty = form.cleaned_data.get('quantity', 0)
                    withdrawal.quantity = volume_qty
                    item.current_stock = F('current_stock') - volume_qty

                else:
                    withdrawal_mode = request.POST.get("withdrawal_mode", "full")

                    if withdrawal_mode == "part":
                        parts_withdrawn = int(request.POST.get("parts_withdrawn") or 0)
                        units_per_item = item.units_per_quantity
                        current_partial = item.accumulated_partial
                        total_units = current_partial + parts_withdrawn

                        full_items = total_units // units_per_item
                        remaining_partial = total_units % units_per_item

                        if full_items > 0:
                            item.current_stock = F('current_stock') - full_items
                        item.accumulated_partial = remaining_partial

                        withdrawal.quantity = full_items
                        withdrawal.parts_withdrawn = parts_withdrawn

                    else:
                        full_items = form.cleaned_data.get("quantity", 0)
                        withdrawal.quantity = full_items
                        item.current_stock = F('current_stock') - full_items

                item.save()
                item.refresh_from_db()
                withdrawal.save()
                return redirect('inventory:dashboard')
            else:
                form.add_error(None, "Product item not found. Check barcode, lot number, or expiry date.")
        else:
            print("❌ Form Errors:", form.errors)

    else:
        form = WithdrawalForm()

    products = Product.objects.filter(items__current_stock__gt=0).distinct().order_by("name")
    return render(request, 'inventory/create_withdrawal.html', {'form': form, 'products': products})
