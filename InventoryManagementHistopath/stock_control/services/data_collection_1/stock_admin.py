from django.shortcuts import render, get_object_or_404
from django.utils.timezone import now
from django.db.models import F
import datetime
from django.utils import timezone
from services.data_collection.data_collection import parse_barcode_data
from services.data_storage.models import Product, ProductItem, Withdrawal, Supplier
from inventory.forms import ProductForm, ProductItemForm
from django.shortcuts import redirect
from stock_control.module_loader import module_flags as get_module_flags

try:
    from solutions.location_tracking.models import LocationStock
except Exception:
    LocationStock = None


def stock_admin(request, product_id=None):
    raw_barcode = request.GET.get("raw", None)
    barcode_parsed_code, parsed_lot, parsed_expiry = None, None, None
    editing_product, editing_lot_item = None, None
    product_form_initial = {}

    if raw_barcode:
        barcode_data = parse_barcode_data(raw_barcode)
        if barcode_data:
            print("[StockAdmin] Parsed barcode data:", barcode_data)
            barcode_parsed_code = barcode_data.get("raw_product_code") or barcode_data.get("product_code")
            barcode_normalized = barcode_data.get("normalized_product_code")
            parsed_lot = barcode_data.get("lot_number")
            parsed_expiry = barcode_data.get("expiry_date")
            if barcode_data.get("product_code"):
                product_form_initial["product_code"] = barcode_data.get("product_code")

            product_form_initial["product_code"] = barcode_data.get("raw_product_code") or barcode_data.get("product_code") or ""

            candidate_codes = _candidate_codes(
                barcode_parsed_code,
                barcode_normalized,
                barcode_data.get("product_code"),
                barcode_data.get("raw_product_code"),
                barcode_data.get("normalized_product_code"),
            )
            print("[StockAdmin] Candidate codes:", candidate_codes)
            for candidate in candidate_codes:
                editing_product = Product.objects.filter(product_code__iexact=candidate).first()
                if editing_product:
                    print("[StockAdmin] Matched product via code:", candidate)
                    break
            # Fallback: locate product via lot number if code lookup failed
            if not editing_product and parsed_lot:
                lot_match = ProductItem.objects.select_related("product").filter(lot_number__iexact=parsed_lot).first()
                if lot_match:
                    editing_product = lot_match.product
                    editing_lot_item = lot_match
                    print("[StockAdmin] Matched product via lot:", parsed_lot)
            if editing_product:
                product_id = editing_product.id
                if parsed_lot and not editing_lot_item:
                    editing_lot_item = ProductItem.objects.filter(product=editing_product, lot_number=parsed_lot).first()

    products = Product.objects.all().order_by('name')
    # Default supplier ref: only set from the product being edited or scanned.
    last_supplier_ref = (
        Product.objects.exclude(supplier_ref__isnull=True)
        .order_by("-id")
        .values_list("supplier_ref_id", flat=True)
        .first()
    ) or None
    product = get_object_or_404(Product, pk=product_id) if product_id else None

    if request.method == "POST":
        product_form = ProductForm(request.POST, instance=product)
        product_item_form = ProductItemForm(request.POST, instance=editing_lot_item)

        if product_form.is_valid() and product_item_form.is_valid():
            saved_product = product_form.save()
            product_item = product_item_form.save(commit=False)
            product_item.product = saved_product
            product_item.save()
            return redirect('data_collection_1:stock_admin')


    else:
        # Prefer the product's existing supplier_ref; if absent but product has a supplier code, try matching by name.
        prefill_supplier_ref = editing_product.supplier_ref_id if (editing_product and editing_product.supplier_ref_id) else None
        if not prefill_supplier_ref and editing_product:
            code_to_name = dict(Product.SUPPLIER_CHOICES)
            supplier_name = code_to_name.get(editing_product.supplier)
            if supplier_name:
                prefill_supplier_ref = Supplier.objects.filter(name__iexact=supplier_name).values_list("id", flat=True).first()

        initial_kwargs = {}
        # Only set initial when there's a supplier_ref on the product
        if prefill_supplier_ref:
            initial_kwargs["supplier_ref"] = prefill_supplier_ref

        if editing_product:
            product_form = ProductForm(instance=editing_product, initial=initial_kwargs)
        else:
            product_form_initial.update(initial_kwargs)
            product_form = ProductForm(initial=product_form_initial)
        product_item_form = ProductItemForm(instance=editing_lot_item)

        if parsed_lot and not editing_lot_item:
            product_item_form.fields['lot_number'].initial = parsed_lot
        if parsed_expiry and not editing_lot_item:
            try:
                product_item_form.fields['expiry_date'].initial = datetime.datetime.strptime(parsed_expiry, "%d.%m.%Y").date()
            except ValueError:
                pass

    low_stock = [p for p in products if sum(item.current_stock for item in p.items.all()) < p.threshold]

    module_flags = get_module_flags()
    location_stocks = {}
    if module_flags.get("location_tracking") and LocationStock:
        stocks = LocationStock.objects.select_related("location", "product_item", "product_item__product").filter(
            product_item__product__in=products
        )
        for stock in stocks:
            location_stocks.setdefault(stock.product_item.product_id, []).append(stock)
        for p in products:
            p.location_stocks = location_stocks.get(p.id, [])

    context = {
        'products': products,
        'product_form': product_form,
        'product_item_form': product_item_form,
        'editing_product': editing_product,
        'low_stock': low_stock,
        'location_stocks': location_stocks,
        'location_tracking_enabled': module_flags.get("location_tracking", False) and LocationStock is not None,
        'now': now(),
    }
    return render(request, 'inventory/stock_admin.html', context)



def delete_lot(request, item_id):
    item = get_object_or_404(ProductItem, id=item_id)
    if request.method == "POST":
        Withdrawal.objects.create(
            product_item=item,
            quantity=item.current_stock,
            withdrawal_type='lot_discard',
            timestamp=timezone.now(),
            user=request.user,
            barcode=None,
            parts_withdrawn=0,
            product_code=item.product.product_code,
            product_name=item.product.name,
            lot_number=item.lot_number,
            expiry_date=item.expiry_date,
        )
        item.delete()
        return redirect('data_collection_1:stock_admin')
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
