# views.py
from collections import defaultdict
import csv
import io
from datetime import timedelta
from io import BytesIO

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import now
from django.db import transaction
from django.http import Http404
import pandas as pd

from inventory.access_control import group_required
from inventory.roles import (
    ROLE_INVENTORY_MANAGER,
    ROLE_STAFF,
    user_is_inventory_manager,
)
from stock_control.module_loader import module_flags as get_module_flags

LEGACY_STAFF_ROLE = "Leica Staff"
from services.analysis.analysis import get_dashboard_data
from services.data_collection.data_collection import parse_barcode_data
from services.data_collection_1.stock_admin import (
    delete_lot as _delete_lot,
    stock_admin as _stock_admin,
)
from services.data_collection_2.create_withdrawal import (
    create_withdrawal as _create_withdrawal,
)
from services.data_storage.models import (
    Product,
    ProductItem,
    PurchaseOrder,
    Supplier,
    Location,
    StockRegistration,
    Withdrawal,
    PurchaseOrderCompletionLog,
)
try:
    from solutions.quality_control.models import QualityCheck
except Exception:
    QualityCheck = None
try:
    from solutions.location_tracking.models import UserLocation
except Exception:
    UserLocation = None

from .forms import (
    AdminUserCreationForm,
    AdminUserEditForm,
    ProductForm,
    SupplierForm,
    LocationForm,
)

class InventoryUploadForm(forms.Form):
    file = forms.FileField(help_text="Upload CSV with columns: code,name,threshold (optional: supplier, lead_time_days, location)")


class ResetInventoryForm(forms.Form):
    RESET_CHOICES = [
        ("clear_lots", "Clear lots (ProductItem records)"),
        ("clear_stock", "Clear stock records (registrations/withdrawals, zero out lots)"),
        ("clear_all", "Clear all inventory records"),
    ]
    action = forms.ChoiceField(widget=forms.RadioSelect, choices=RESET_CHOICES)




# ✅ Function to check if the user is an admin
def is_admin(user):
    return user_is_inventory_manager(user)

@group_required([ROLE_INVENTORY_MANAGER])
def manage_inventory(request):
    return render(request, "manage_inventory.html")

@group_required([ROLE_INVENTORY_MANAGER, ROLE_STAFF, LEGACY_STAFF_ROLE])
def view_dashboard(request):
    return render(request, "dashboard.html")

# ✅ Admin-only view to list all users
@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def manage_users(request):
    users = User.objects.order_by("username")
    location_map = {}
    if UserLocation:
        assignments = UserLocation.objects.select_related("location").filter(user__in=users)
        for assignment in assignments:
            location_map[assignment.user_id] = assignment.location.name
    return render(request, 'registration/manage_users.html', {'users': users, 'user_locations': location_map})

# ✅ Admin-only view to register a new user
@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def register_user(request):
    if request.method == 'POST':
        form = AdminUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('inventory:manage_users')
    else:
        form = AdminUserCreationForm()
    return render(request, 'registration/register_user.html', {'form': form})

# ✅ Admin-only view to edit a user
@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('inventory:manage_users')
    else:
        form = AdminUserEditForm(instance=user)
    return render(request, 'registration/edit_user.html', {'form': form, 'user_obj': user})

# ✅ Admin-only view to delete a user
@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        user.delete()
        return redirect('inventory:manage_users')
    return render(request, 'registration/delete_user.html', {'user_obj': user})

@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_STAFF, LEGACY_STAFF_ROLE])
def inventory_dashboard(request):
    context = get_dashboard_data()

    # 1. Low stock alerts
    low_stock_alerts = [
        p for p in Product.objects.prefetch_related("items").all()
        if sum(item.current_stock for item in p.items.all()) < p.threshold
    ]
    has_low_stock_alerts = len(low_stock_alerts) > 0

    # 2. Expired lots
    has_expired_lot_alerts = ProductItem.objects.filter(expiry_date__lte=now().date()).exists()

    # 3. Delayed deliveries
    has_delayed_delivery_alerts = PurchaseOrder.objects.filter(
        expected_delivery__lt=now()
    ).exclude(status="Delivered").exists()

    # 4. Products with missing threshold
    products_with_zero_threshold = Product.objects.filter(threshold=0)
    has_missing_thresholds = products_with_zero_threshold.exists()

    # 5. Duplicate product names
    # Normalize names: strip spaces and convert to lowercase
    raw_names = Product.objects.values_list("name", flat=True)
    normalized_name_map = defaultdict(list)

    for name in raw_names:
        normalized = name.strip().lower()
        normalized_name_map[normalized].append(name)

    # Only consider real duplicates (two or more different entries mapping to same normalized form)
    duplicate_product_names = [
        names[0] for names in normalized_name_map.values() if len(set(names)) > 1
    ]

    # 6. User count
    total_users = User.objects.count()
    total_locations = Location.objects.count()
    total_products = Product.objects.count()

    context.update({
        "has_low_stock_alerts": has_low_stock_alerts,
        "has_expired_lot_alerts": has_expired_lot_alerts,
        "has_delayed_delivery_alerts": has_delayed_delivery_alerts,
        "has_missing_thresholds": has_missing_thresholds,
        "duplicate_product_names": duplicate_product_names,
        "total_users": total_users,
        "total_locations": total_locations,
        "total_products": total_products,
    })

    return render(request, "inventory/dashboard.html", context)

@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def stock_admin(request, product_id=None):
    response = _stock_admin(request, product_id=product_id)
    if isinstance(response, dict) and response.get("redirect"):
        return redirect('inventory:stock_admin')
    return response

@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def delete_lot(request, item_id):
    response = _delete_lot(request, item_id)
    if isinstance(response, dict) and response.get("redirect"):
        return redirect('inventory:stock_admin')
    return response


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_STAFF, LEGACY_STAFF_ROLE])
def create_withdrawal(request):
    return _create_withdrawal(request)

####################################





FILTER_OPTIONS = [
    ("all", "Show All"),
    ("in_stock", "In Stock"),
    ("low_stock", "Low Stock"),
]
if QualityCheck:
    FILTER_OPTIONS.extend([
        ("qc_passed", "QC Passed"),
        ("qc_pending", "QC Pending"),
    ])


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_STAFF, LEGACY_STAFF_ROLE])
def product_list(request):
    filter_key = request.GET.get("filter", "all")
    valid_filters = {key for key, _ in FILTER_OPTIONS}
    if filter_key not in valid_filters:
        filter_key = "all"

    barcode_value = (request.GET.get("barcode") or "").strip()
    products_qs = Product.objects.select_related("supplier_ref", "location").prefetch_related("items")

    if barcode_value:
        parsed = parse_barcode_data(barcode_value)
        product_code = ""
        if parsed:
            product_code = (parsed.get("product_code") or "").strip()
        else:
            product_code = barcode_value

        lookup_codes = []
        for code in (product_code, barcode_value):
            if not code:
                continue
            lookup_codes.append(code)
            if code.isdigit():
                lookup_codes.append(code.lstrip("0"))

        matched_product = None
        for code in lookup_codes:
            matched_product = Product.objects.filter(product_code__iexact=code).first()
            if matched_product:
                break
        if matched_product:
            products = products_qs.filter(pk=matched_product.pk)
        else:
            products = products_qs
            messages.error(request, "No product matches the scanned barcode.")
    else:
        products = products_qs

    product_ids = [p.id for p in products]
    qc_map = {}
    location_stock_map = {}
    if QualityCheck and product_ids:
        for qc in QualityCheck.objects.filter(product_item__product_id__in=product_ids):
            product_id = qc.product_item.product_id
            qc_map.setdefault(product_id, []).append(qc)
    module_flags = get_module_flags()
    location_tracking_enabled = False
    LocationStockModel = None
    if module_flags.get("location_tracking"):
        try:
            from solutions.location_tracking.models import LocationStock as LocationStockModel
            location_tracking_enabled = True
        except Exception:
            LocationStockModel = None
            location_tracking_enabled = False
    if location_tracking_enabled and product_ids and LocationStockModel:
        stocks = LocationStockModel.objects.select_related("location", "product_item", "product_item__product").filter(
            product_item__product_id__in=product_ids
        )
        for stock in stocks:
            location_stock_map.setdefault(stock.product_item.product_id, []).append(stock)

    def matches(product):
        if filter_key == "in_stock":
            return product.total_stock > 0
        if filter_key == "low_stock":
            return product.is_low_stock
        if QualityCheck:
            if filter_key == "qc_passed":
                return product.qc_passed
            if filter_key == "qc_pending":
                return product.qc_pending
        return True

    visible_products = []
    for product in products:
        product.full_items = product.get_full_items_in_stock()
        product.remaining_parts = product.get_remaining_parts()
        product.total_stock = sum(item.current_stock for item in product.items.all())
        product.is_low_stock = product.total_stock < product.threshold
        if QualityCheck:
            qc_checks = qc_map.get(product.id, [])
            qc_passed = any(
                qc.status == QualityCheck.STATUS_COMPLETED and qc.result == "pass"
                for qc in qc_checks
            )
            product.qc_passed = qc_passed
            product.qc_pending = product.total_stock > 1 and not qc_passed
        else:
            product.qc_passed = False
            product.qc_pending = False
        product.location_stocks = location_stock_map.get(product.id, [])
        if matches(product):
            visible_products.append(product)

    return render(request, 'inventory/product_list.html', {
        'products': visible_products,
        'filter_key': filter_key,
        'filter_options': FILTER_OPTIONS,
        'location_tracking_enabled': location_tracking_enabled,
        'barcode_value': barcode_value,
    })


@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def manage_suppliers(request):
    # Ensure default suppliers exist so they appear in the table and can be mapped.
    with transaction.atomic():
        Supplier.objects.get_or_create(name="Leica")
        Supplier.objects.get_or_create(name="Third Party")

    supplier_id = request.GET.get("supplier_id")
    supplier_instance = None
    if supplier_id:
        supplier_instance = get_object_or_404(Supplier, pk=supplier_id)

    if request.method == "POST":
        supplier_instance = None
        if request.POST.get("supplier_id"):
            supplier_instance = get_object_or_404(Supplier, pk=request.POST["supplier_id"])
        form = SupplierForm(request.POST, instance=supplier_instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Supplier saved successfully.")
            return redirect('inventory:manage_suppliers')
    else:
        form = SupplierForm(instance=supplier_instance)

    suppliers, _, _ = _build_supplier_product_map()

    return render(
        request,
        "inventory/manage_suppliers.html",
        {
            "form": form,
            "suppliers": suppliers,
            "editing": supplier_instance,
        },
    )


@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def import_inventory(request):
    form = InventoryUploadForm()
    reset_form = ResetInventoryForm(initial={"action": "clear_lots"})
    summary = None
    errors = []

    def parse_records_from_text(text):
        # Prefer CSV when commas are present; otherwise treat as whitespace-separated rows.
        if "," in text:
            return csv.DictReader(io.StringIO(text))
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return []
        data_lines = lines[1:] if len(lines) > 1 else lines
        records = []
        for ln in data_lines:
            parts = ln.split()
            if len(parts) < 2:
                continue
            code = parts[0]
            threshold = parts[-1] if parts[-1].isdigit() else ""
            name = " ".join(parts[1:-1] if parts[-1].isdigit() else parts[1:])
            records.append({"code": code, "name": name, "threshold": threshold})
        return records

    def get_val(row, keys):
        # Normalize keys for loose matching (case/spacing-insensitive)
        lower_map = {str(k).strip().lower(): v for k, v in row.items()}
        for k in keys:
            if k in row and row[k]:
                return row[k]
            lk = str(k).strip().lower()
            if lk in lower_map and lower_map[lk]:
                return lower_map[lk]
        return ""

    def to_str(val):
        if val is None:
            return ""
        try:
            return str(val).strip()
        except Exception:
            return ""

    if request.method == "POST":
        if "reset_action" in request.POST:
            reset_form = ResetInventoryForm(request.POST)
            if reset_form.is_valid():
                action = reset_form.cleaned_data["action"]
                with transaction.atomic():
                    if action in ("clear_stock", "clear_all"):
                        Withdrawal.objects.all().delete()
                        StockRegistration.objects.all().delete()
                        ProductItem.objects.update(current_stock=0, accumulated_partial=0)
                        PurchaseOrderCompletionLog.objects.all().delete()
                        PurchaseOrder.objects.all().delete()
                    if action in ("clear_lots", "clear_all"):
                        ProductItem.objects.all().delete()
                    if action == "clear_all":
                        Product.objects.all().delete()
                messages.success(request, f"Inventory reset performed: {dict(reset_form.fields['action'].choices).get(action)}")
        else:
            form = InventoryUploadForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.cleaned_data["file"]
                filename = upload.name.lower()

                if filename.endswith((".xlsx", ".xls")):
                    df = pd.read_excel(BytesIO(upload.read()))
                    reader = df.to_dict(orient="records")
                else:
                    raw = upload.read().decode("utf-8")
                    reader = parse_records_from_text(raw)
                created = updated = 0

                def parse_int(val, default=0):
                    try:
                        return int(val)
                    except (TypeError, ValueError):
                        return default

                with transaction.atomic():
                    for idx, row in enumerate(reader, start=1):
                        code = to_str(get_val(row, ["code", "product_code", "Code", "Item code", "item_code"]))
                        name = to_str(get_val(row, ["name", "product", "Product Name"]))
                        if not code or not name:
                            errors.append(f"Row {idx}: missing code or name")
                            continue

                        threshold = parse_int(row.get("threshold") or row.get("min_qty") or row.get("Minimum Stock Level (Unopened)"))
                        supplier_name = to_str(row.get("supplier"))
                        supplier_choice = to_str(row.get("supplier_code")).upper() or "LEICA"
                        if supplier_choice not in dict(Product.SUPPLIER_CHOICES):
                            supplier_choice = "THIRD_PARTY" if supplier_name else "LEICA"

                        supplier_ref = None
                        if supplier_name:
                            supplier_ref, _ = Supplier.objects.get_or_create(name=supplier_name)

                        location_name = to_str(row.get("location"))
                        location = None
                        if location_name:
                            location, _ = Location.objects.get_or_create(name=location_name)

                        lead_time_days = parse_int(row.get("lead_time_days") or row.get("lead_time"))
                        lead_time = timedelta(days=lead_time_days or 0)

                        defaults = {
                            "name": name,
                            "threshold": threshold,
                            "supplier": supplier_choice,
                            "supplier_ref": supplier_ref,
                            "location": location,
                            "lead_time": lead_time,
                        }
                        _, created_flag = Product.objects.update_or_create(
                            product_code=code,
                            defaults=defaults,
                        )
                        if created_flag:
                            created += 1
                        else:
                            updated += 1

                summary = {"created": created, "updated": updated, "errors": len(errors)}
                if errors:
                    messages.warning(request, f"Imported with {len(errors)} issues. Created {created}, updated {updated}.")
                else:
                    messages.success(request, f"Imported {created} new, updated {updated}.")

    return render(
        request,
        "inventory/import_inventory.html",
        {"form": form, "reset_form": reset_form, "summary": summary, "errors": errors},
    )


def _build_supplier_product_map():
    suppliers = list(Supplier.objects.prefetch_related("products").order_by("name"))

    # Build a mapping so default suppliers also show products whose supplier code matches.
    code_to_label = dict(Product.SUPPLIER_CHOICES)
    name_to_supplier = {s.name.lower(): s for s in suppliers}
    supplier_to_products = {s.id: list(s.products.all()) for s in suppliers}

    all_products = Product.objects.select_related("supplier_ref", "location").prefetch_related("items").all()
    for product in all_products:
        if product.supplier_ref_id:
            supplier_to_products.setdefault(product.supplier_ref_id, []).append(product)
            continue

        label = code_to_label.get(product.supplier)
        if not label:
            continue
        mapped_supplier = name_to_supplier.get(label.lower())
        if mapped_supplier:
            supplier_to_products.setdefault(mapped_supplier.id, []).append(product)

    for supplier in suppliers:
        supplier.mapped_products = supplier_to_products.get(supplier.id, [])

    return suppliers, supplier_to_products, name_to_supplier


def _build_location_product_map():
    locations = list(Location.objects.prefetch_related("products").order_by("name"))
    location_to_products = {loc.id: list(loc.products.all()) for loc in locations}

    # Allow products with a location assignment to be included even if prefetch missed
    all_products = Product.objects.select_related("location").prefetch_related("items").all()
    for product in all_products:
        if product.location_id:
            location_to_products.setdefault(product.location_id, []).append(product)

    # If location tracking module exists, include products that have LocationStock entries
    try:
        from solutions.location_tracking.models import LocationStock

        location_stock_rows = LocationStock.objects.select_related(
            "location",
            "product_item",
            "product_item__product",
        )
        for row in location_stock_rows:
            loc_id = row.location_id
            product = row.product_item.product
            location_to_products.setdefault(loc_id, []).append(product)
    except Exception:
        pass

    for loc in locations:
        # Deduplicate by product id
        seen = set()
        mapped = []
        for prod in location_to_products.get(loc.id, []):
            if prod.id in seen:
                continue
            seen.add(prod.id)
            mapped.append(prod)
        loc.mapped_products = mapped

    return locations, location_to_products


@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def supplier_products(request, supplier_id):
    suppliers, supplier_to_products, _ = _build_supplier_product_map()
    supplier = next((s for s in suppliers if s.id == supplier_id), None)
    if not supplier:
        raise Http404("Supplier not found")

    mapped_products = supplier_to_products.get(supplier.id, [])
    for product in mapped_products:
        product.total_stock = sum(item.current_stock for item in product.items.all())
        product.location_name = product.location.name if product.location else "—"

    return render(
        request,
        "inventory/supplier_products.html",
        {
            "supplier": supplier,
            "products": mapped_products,
        },
    )


@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def location_products(request, location_id):
    locations, location_to_products = _build_location_product_map()
    location = next((l for l in locations if l.id == location_id), None)
    if not location:
        raise Http404("Location not found")

    mapped_products = location_to_products.get(location.id, [])
    for product in mapped_products:
        product.total_stock = sum(item.current_stock for item in product.items.all())
        product.location_name = product.location.name if product.location else "—"

    return render(
        request,
        "inventory/location_products.html",
        {
            "location": location,
            "products": mapped_products,
        },
    )


@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def manage_locations(request):
    location_id = request.GET.get("location_id")
    location_instance = None
    if location_id:
        location_instance = get_object_or_404(Location, pk=location_id)

    if request.method == "POST":
        location_instance = None
        if request.POST.get("location_id"):
            location_instance = get_object_or_404(Location, pk=request.POST["location_id"])
        form = LocationForm(request.POST, instance=location_instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Location saved successfully.")
            return redirect('inventory:manage_locations')
    else:
        form = LocationForm(instance=location_instance)

    locations, _ = _build_location_product_map()
    return render(
        request,
        "inventory/manage_locations.html",
        {
            "form": form,
            "locations": locations,
            "editing": location_instance,
        },
    )


@login_required
@user_passes_test(is_admin, login_url='inventory:dashboard')
def manage_product_codes(request):
    product_id = request.GET.get("product_id")
    product_instance = None
    if product_id:
        product_instance = get_object_or_404(Product, pk=product_id)

    if request.method == "POST":
        product_instance = None
        if request.POST.get("product_id"):
            product_instance = get_object_or_404(Product, pk=request.POST["product_id"])
        form = ProductForm(request.POST, instance=product_instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Product saved successfully.")
            return redirect('inventory:manage_product_codes')
    else:
        form = ProductForm(instance=product_instance)

    products = Product.objects.select_related("supplier_ref", "location").order_by("product_code")
    return render(
        request,
        "inventory/manage_product_codes.html",
        {
            "form": form,
            "products": products,
            "editing": product_instance,
        },
    )


@login_required
def help_page(request):
    return render(request, "inventory/help.html")
