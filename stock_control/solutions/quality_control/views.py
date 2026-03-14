from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Prefetch, Sum, Q
from django.shortcuts import redirect, render
from django.utils import timezone

from inventory.access_control import group_required
from inventory.location_utils import (
    ACTIVE_USER_LOCATION_SESSION_KEY,
    build_user_location_state,
    coerce_location_id,
    get_user_location_choices,
    get_user_location_ids,
    get_product_ids_for_locations,
)
from inventory.roles import (
    ROLE_INVENTORY_MANAGER,
    ROLE_TEAM_MANAGER,
    user_has_role,
    user_is_inventory_manager,
)
from services.data_collection.data_collection import parse_barcode_data
from services.data_storage.models import Product, ProductItem
from stock_control.module_loader import module_flags as get_module_flags

from .forms import QualityCheckForm
from .models import QualityCheck

User = get_user_model()


def is_inventory_admin(user):
    if not user.is_authenticated:
        return False
    if user_is_inventory_manager(user):
        return True
    return user_has_role(user, ROLE_TEAM_MANAGER)


def _get_location_scope(user):
    location_tracking_enabled = get_module_flags().get("location_tracking", False)
    team_manager_scope = (
        location_tracking_enabled
        and user_has_role(user, ROLE_TEAM_MANAGER)
        and not user_is_inventory_manager(user)
    )
    allowed_location_ids = get_user_location_ids(user) if team_manager_scope else set()
    allowed_product_ids = (
        get_product_ids_for_locations(allowed_location_ids) if allowed_location_ids else set()
    )
    if not team_manager_scope:
        allowed_product_ids = None
    return location_tracking_enabled, team_manager_scope, allowed_location_ids, allowed_product_ids


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_TEAM_MANAGER])
def list_checks(request):
    (
        location_tracking_enabled,
        team_manager_scope,
        allowed_location_ids,
        allowed_product_ids,
    ) = _get_location_scope(request.user)
    location_state = build_user_location_state(
        request.user, request.session.get(ACTIVE_USER_LOCATION_SESSION_KEY)
    )
    selected_location_id = location_state["selected_id"]
    requested_location_id = coerce_location_id(request.GET.get("location_id"))
    if requested_location_id is not None:
        if not location_state["allowed_ids"] or requested_location_id in location_state["allowed_ids"]:
            selected_location_id = requested_location_id
    if selected_location_id:
        request.session[ACTIVE_USER_LOCATION_SESSION_KEY] = selected_location_id
    location_filter_ids = (
        get_product_ids_for_locations({selected_location_id}) if selected_location_id else None
    )
    location_names = [loc.name for loc in location_state["locations"]] if team_manager_scope else []
    checks = (
        QualityCheck.objects.select_related(
            "product_item",
            "product_item__product",
            "performed_by",
            "signed_off_by",
            "location",
        )
        .order_by("-created_at")
    )
    if team_manager_scope:
        if allowed_location_ids:
            checks = checks.filter(
                Q(location_id__in=allowed_location_ids)
                | Q(location_id__isnull=True, product_item__product_id__in=allowed_product_ids)
            )
        else:
            checks = checks.none()
    return render(
        request,
        "quality_control/list_checks.html",
        {
            "checks": checks,
            "team_manager_scope": team_manager_scope,
            "location_tracking_enabled": location_tracking_enabled,
            "user_locations": location_names,
        },
    )


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_TEAM_MANAGER])
def lot_status(request):
    """Show lots for a selected/scanned product with latest QC status."""
    raw_messages = messages.get_messages(request)
    qc_messages = [m for m in raw_messages if m.level_tag in ("error", "warning")]

    (
        location_tracking_enabled,
        team_manager_scope,
        allowed_location_ids,
        allowed_product_ids,
    ) = _get_location_scope(request.user)
    location_state = build_user_location_state(
        request.user, request.session.get(ACTIVE_USER_LOCATION_SESSION_KEY)
    )
    selected_location_id = coerce_location_id(request.GET.get("location_id")) or location_state["selected_id"]
    if selected_location_id and location_state["allowed_ids"] and selected_location_id not in location_state["allowed_ids"]:
        selected_location_id = location_state["selected_id"]
    if selected_location_id:
        request.session[ACTIVE_USER_LOCATION_SESSION_KEY] = selected_location_id
    location_filter_ids = (
        get_product_ids_for_locations({selected_location_id}) if selected_location_id else None
    )
    location_names = [loc.name for loc in location_state["locations"]] if team_manager_scope else []

    products = (
        Product.objects.filter(items__current_stock__gt=0)
        .order_by("name")
        .distinct()
    )
    selection_required = location_tracking_enabled and location_state["selection_required"]
    if selection_required and not selected_location_id:
        products = Product.objects.none()
    else:
        filtered_ids = None
        if allowed_product_ids is not None:
            filtered_ids = set(allowed_product_ids)
        if location_filter_ids is not None:
            if filtered_ids is None:
                filtered_ids = set(location_filter_ids)
            else:
                filtered_ids &= set(location_filter_ids)
        if filtered_ids is not None:
            if filtered_ids:
                products = products.filter(id__in=filtered_ids)
            else:
                products = Product.objects.none()
    selected_product = None

    barcode_value = (request.GET.get("barcode") or "").strip()
    product_id = request.GET.get("product_id")

    if barcode_value:
        parsed = parse_barcode_data(barcode_value)
        product_code = ""
        qr_numeric_code = ""
        if parsed:
            product_code = (parsed.get("product_code") or "").strip()
            qr_numeric_code = (parsed.get("qr_numeric_code") or "").strip()
        else:
            product_code = barcode_value

        lookup_codes = [product_code, barcode_value, qr_numeric_code]
        if product_code.isdigit():
            lookup_codes.append(product_code.lstrip("0"))
        if qr_numeric_code and qr_numeric_code.isdigit():
            lookup_codes.append(qr_numeric_code.lstrip("0"))

        for code in lookup_codes:
            if not code:
                continue
            selected_product = Product.objects.filter(product_code__iexact=code).first()
            if not selected_product and code.isdigit():
                selected_product = Product.objects.filter(
                    qr_numeric_code=int(code)
                ).first()
            if selected_product:
                break
        if not selected_product:
            messages.error(request, "No product matches the scanned barcode.")

    if not selected_product and product_id:
        selected_product = Product.objects.filter(pk=product_id).first()
        if not selected_product:
            messages.error(request, "Selected product not found.")

    valid_product_ids = None
    if allowed_product_ids is not None:
        valid_product_ids = set(allowed_product_ids)
    if location_filter_ids is not None:
        if valid_product_ids is None:
            valid_product_ids = set(location_filter_ids)
        else:
            valid_product_ids &= set(location_filter_ids)

    if selection_required and not selected_location_id:
        selected_product = None
    elif valid_product_ids is not None and selected_product and selected_product.id not in valid_product_ids:
        messages.error(request, "You do not have access to this product's locations.")
        selected_product = None

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
        if selected_location_id and not (selected_product.location_id == selected_location_id):
            allowed_item_ids = set()
            try:
                from solutions.location_tracking.models import LocationStock

                allowed_item_ids.update(
                    LocationStock.objects.filter(
                        location_id=selected_location_id,
                        product_item__product=selected_product,
                    ).values_list("product_item_id", flat=True)
                )
            except Exception:
                pass
            if allowed_item_ids:
                items = items.filter(id__in=allowed_item_ids)
            else:
                items = ProductItem.objects.none()
        if selection_required and not selected_location_id:
            items = ProductItem.objects.none()

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
            "team_manager_scope": team_manager_scope,
            "location_tracking_enabled": location_tracking_enabled,
            "location_choices": location_state["locations"],
            "location_selection_required": selection_required,
            "selected_location_id": selected_location_id,
            "user_locations": location_names,
        },
    )


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def create_check(request):
    (
        location_tracking_enabled,
        team_manager_scope,
        allowed_location_ids,
        allowed_product_ids,
    ) = _get_location_scope(request.user)
    location_state = build_user_location_state(
        request.user, request.session.get(ACTIVE_USER_LOCATION_SESSION_KEY)
    )
    selected_location_id = location_state["selected_id"]
    selection_required = location_state["selection_required"]
    allowed_choice_ids = location_state["allowed_ids"]
    location_error = None

    def _compute_allowed_ids(current_location_id):
        location_filtered = (
            get_product_ids_for_locations({current_location_id}) if current_location_id else None
        )
        ids = None
        if allowed_product_ids is not None:
            ids = set(allowed_product_ids)
        if location_filtered is not None:
            if ids is None:
                ids = set(location_filtered)
            else:
                ids &= set(location_filtered)
        if selection_required and not current_location_id:
            return set()
        return ids

    resolved_allowed_ids = _compute_allowed_ids(selected_location_id)
    form_kwargs = {}

    def _refresh_form_kwargs():
        if resolved_allowed_ids is not None:
            form_kwargs["allowed_product_ids"] = list(resolved_allowed_ids)
        else:
            form_kwargs.pop("allowed_product_ids", None)

    _refresh_form_kwargs()

    if request.method == "POST":
        posted_location_id = coerce_location_id(request.POST.get("selected_location"))
        if posted_location_id is not None:
            selected_location_id = posted_location_id
            resolved_allowed_ids = _compute_allowed_ids(selected_location_id)
            _refresh_form_kwargs()
        if location_tracking_enabled and allowed_choice_ids:
            if selection_required and not selected_location_id:
                location_error = "Select a location before recording a quality check."
            elif selected_location_id and selected_location_id not in allowed_choice_ids:
                location_error = "Invalid location selected."
        form = QualityCheckForm(request.POST, **form_kwargs)
        if form.is_valid() and not location_error:
            qc = form.save(commit=False)
            qc.performed_by = request.user
            if selected_location_id:
                qc.location_id = selected_location_id
            if qc.result or qc.status == QualityCheck.STATUS_COMPLETED:
                qc.status = QualityCheck.STATUS_COMPLETED
                qc.signed_off_by = request.user
                qc.signed_off_at = timezone.now()
            qc.save()
            if selected_location_id:
                request.session[ACTIVE_USER_LOCATION_SESSION_KEY] = selected_location_id
            return redirect("quality_control:list_checks")
        elif location_error:
            form.add_error(None, location_error)
    else:
        form = QualityCheckForm(**form_kwargs)
    return render(
        request,
        "quality_control/create_check.html",
        {
            "form": form,
            "location_choices": location_state["locations"],
            "location_selection_required": location_tracking_enabled and selection_required,
            "selected_location_id": selected_location_id,
        },
    )
