from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils.timezone import now

from inventory.access_control import group_required
from inventory.roles import (
    ROLE_INVENTORY_MANAGER,
    ROLE_STAFF,
    ROLE_SUPPLIER,
    user_has_role,
    user_is_inventory_manager,
)
from services.analysis.analysis import (
    inventory_analysis_forecasting as _inventory_analysis_forecasting,
)
from services.data_storage.models import Product, ProductItem, Withdrawal, Location
from services.reporting.reporting import download_report as _download_report
from django.db.models import Sum, F
from decimal import Decimal

EXPIRED_RANGE_OPTIONS = {
    "now": {"label": "Expired", "days": 0},
    "week": {"label": "Next 1 Week", "days": 7},
    "month": {"label": "Next 1 Month", "days": 30},
}


def is_inventory_admin(user):
    return user_is_inventory_manager(user)


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def inventory_analysis_forecasting(request):
    return _inventory_analysis_forecasting(request)


@login_required
@user_passes_test(is_inventory_admin, login_url="inventory:dashboard")
def download_report(request):
    return _download_report(request)


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_STAFF, "Leica Staff"])
def track_withdrawals(request):
    withdrawals = (
        Withdrawal.objects.select_related("product_item", "user")
        .order_by("-timestamp")
    )
    staff_only = user_has_role(request.user, ROLE_STAFF) and not user_is_inventory_manager(request.user)
    if staff_only:
        withdrawals = withdrawals.filter(user=request.user)
    for withdrawal in withdrawals:
        withdrawal.full_items = withdrawal.get_full_items_withdrawn()
        withdrawal.partial_items = withdrawal.get_partial_items_withdrawn()
    return render(
        request,
        "analytics/track_withdrawals.html",
        {"withdrawals": withdrawals, "staff_only": staff_only},
    )


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_SUPPLIER])
def track_low_lots(request):
    low_lots = []
    for product in Product.objects.prefetch_related("items").all():
        total_stock = sum(item.current_stock for item in product.items.all())
        if total_stock < product.threshold:
            next_expiry = product.items.order_by("expiry_date").first()
            low_lots.append(
                {
                    "product": product,
                    "total_stock": total_stock,
                    "threshold": product.threshold,
                    "next_expiry": next_expiry.expiry_date if next_expiry else None,
                }
            )

    low_lots.sort(key=lambda entry: entry["total_stock"])
    return render(
        request,
        "analytics/track_low_lots.html",
        {"low_lots": low_lots},
    )


@login_required
@group_required([ROLE_INVENTORY_MANAGER, ROLE_SUPPLIER])
def track_expired_lots(request):
    today = now().date()
    range_key = request.GET.get("range", "now")
    if range_key not in EXPIRED_RANGE_OPTIONS:
        range_key = "now"

    option = EXPIRED_RANGE_OPTIONS[range_key]
    if range_key == "now":
        expired_items = ProductItem.objects.select_related("product").filter(
            expiry_date__lt=today
        )
    else:
        upper = today + timedelta(days=option["days"])
        expired_items = ProductItem.objects.select_related("product").filter(
            expiry_date__range=(today, upper)
        )

    expired_items = expired_items.order_by("expiry_date")
    return render(
        request,
        "analytics/track_expired_lots.html",
        {
            "expired_items": expired_items,
            "today": today,
            "range_options": [
                {"value": key, "label": value["label"]}
                for key, value in EXPIRED_RANGE_OPTIONS.items()
            ],
            "selected_range": range_key,
        },
    )


@login_required
@group_required([ROLE_INVENTORY_MANAGER])
def intelligence(request):
    """Experimental intelligence page: allocation, expiry heatmap, slow movers."""
    # ----- Location Allocation Optimization -----
    location_stocks = []
    location_transfer_recs = []
    try:
        from solutions.location_tracking.models import LocationStock

        location_stocks = list(
            LocationStock.objects.select_related("location", "product_item", "product_item__product").order_by(
                "product_item__product__name", "location__name"
            )
        )
    except Exception:
        LocationStock = None

    product_location_map = {}
    product_meta = {}

    if LocationStock and location_stocks:
        for row in location_stocks:
            pid = row.product_item.product_id
            loc_id = row.location_id
            product_location_map.setdefault(pid, {})[loc_id] = Decimal(row.quantity)
            product_meta[pid] = row.product_item.product

        for pid, loc_map in product_location_map.items():
            product = product_meta.get(pid)
            if not product:
                continue
            locations_qty = list(loc_map.items())
            total = sum(loc_map.values())
            if total <= 0 or not locations_qty:
                continue
            target_per_loc = max(Decimal("1"), Decimal(product.threshold) / Decimal(len(locations_qty) or 1))
            surplus = []
            deficit = []
            for loc_id, qty in locations_qty:
                if qty > target_per_loc:
                    surplus.append([loc_id, qty - target_per_loc])
                elif qty < target_per_loc:
                    deficit.append([loc_id, target_per_loc - qty])
            surplus.sort(key=lambda x: x[1], reverse=True)
            deficit.sort(key=lambda x: x[1], reverse=True)
            for s_loc, s_amt in surplus:
                for d_idx, (d_loc, d_need) in enumerate(deficit):
                    if s_amt <= 0:
                        break
                    move_amt = min(s_amt, d_need)
                    if move_amt <= 0:
                        continue
                    location_transfer_recs.append(
                        {
                            "product": product,
                            "from_location_id": s_loc,
                            "to_location_id": d_loc,
                            "quantity": float(move_amt) if move_amt % 1 else int(move_amt),
                        }
                    )
                    s_amt -= move_amt
                    deficit[d_idx][1] -= move_amt

    # ----- Expiry & Ageing Heatmap -----
    today = now().date()
    buckets = [
        ("0-15d", 0, 15),
        ("16-30d", 16, 30),
        ("31-60d", 31, 60),
        (">60d", 61, 99999),
    ]
    bucket_counts = {label: {"lots": 0, "qty": Decimal("0")} for label, _, _ in buckets}
    at_risk_lots = []
    for item in ProductItem.objects.select_related("product").all():
        days = (item.expiry_date - today).days
        qty = Decimal(item.current_stock)
        bucket_label = None
        for label, low, high in buckets:
            if low <= days <= high:
                bucket_label = label
                break
        if bucket_label:
            bucket_counts[bucket_label]["lots"] += 1
            bucket_counts[bucket_label]["qty"] += qty
        if days <= 30:
            at_risk_lots.append(
                {
                    "product": item.product,
                    "lot": item.lot_number,
                    "expiry": item.expiry_date,
                    "days": days,
                    "qty": qty,
                }
            )
    at_risk_lots.sort(key=lambda r: r["days"])

    # ----- Stock Turnover & Slow Movers -----
    window_days = 90
    start_date = today - timedelta(days=window_days)
    withdrawals = (
        Withdrawal.objects.filter(timestamp__date__gte=start_date)
        .values("product_item__product_id")
        .annotate(total=Sum("quantity"))
    )
    withdraw_map = {row["product_item__product_id"]: float(row["total"] or 0) for row in withdrawals}

    slow_movers = []
    for product in Product.objects.prefetch_related("items").all():
        total_stock = float(sum(i.current_stock for i in product.items.all()))
        total_withdrawn = withdraw_map.get(product.id, 0.0)
        turnover = total_withdrawn / total_stock if total_stock > 0 else 0.0
        if total_withdrawn < 1 or turnover < 0.2:
            slow_movers.append(
                {
                    "product": product,
                    "total_stock": total_stock,
                    "withdrawn": total_withdrawn,
                    "turnover": round(turnover, 2),
                }
            )
    slow_movers.sort(key=lambda x: x["turnover"])

    # Resolve location names for recommendations
    location_lookup = {loc.id: loc for loc in Location.objects.all()}
    for rec in location_transfer_recs:
        rec["from_location"] = location_lookup.get(rec["from_location_id"])
        rec["to_location"] = location_lookup.get(rec["to_location_id"])

    # Charts data prep
    rec_totals = {}
    for rec in location_transfer_recs:
        key = f"{rec['product'].product_code}"
        rec_totals[key] = rec_totals.get(key, 0) + float(rec["quantity"])
    allocation_chart_labels = list(rec_totals.keys())[:10]
    allocation_chart_values = [rec_totals[k] for k in allocation_chart_labels]

    expiry_labels = list(bucket_counts.keys())
    expiry_values = [float(bucket_counts[k]["qty"]) for k in expiry_labels]

    slow_labels = [row["product"].product_code for row in slow_movers[:12]]
    slow_turnover = [row["turnover"] for row in slow_movers[:12]]

    context = {
        "location_transfer_recs": location_transfer_recs,
        "bucket_counts": bucket_counts,
        "at_risk_lots": at_risk_lots[:20],
        "slow_movers": slow_movers[:25],
        "window_days": window_days,
        "allocation_chart_labels": allocation_chart_labels,
        "allocation_chart_values": allocation_chart_values,
        "expiry_labels": expiry_labels,
        "expiry_values": expiry_values,
        "slow_labels": slow_labels,
        "slow_turnover": slow_turnover,
    }
    return render(request, "analytics/intelligence.html", context)
