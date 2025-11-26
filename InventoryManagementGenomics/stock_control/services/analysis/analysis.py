import json
import pandas as pd
from datetime import timedelta
from django.utils.timezone import now
from django.shortcuts import render
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import datetime
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from services.data_storage.models import Product, ProductItem, Withdrawal, PurchaseOrder, Supplier, Location

def get_dashboard_data():
    # 1. Stock Level Status
    products = Product.objects.all()
    stock_labels = []
    stock_values = []
    threshold_values = []
    stock_names = []
    for product in products:
        total_stock = float(product.get_full_items_in_stock())
        # Only include products with stock > 0 and either below threshold or at least 2 above
        if total_stock <= 0:
            continue
        threshold = product.threshold
        if total_stock < threshold or total_stock >= (threshold + 2):
            stock_labels.append(product.product_code)
            stock_values.append(total_stock)
            threshold_values.append(threshold)
            stock_names.append(product.name)

    # 2. Stock Distribution by Supplier
    supplier_choice_map = dict(Product.SUPPLIER_CHOICES)
    supplier_data = (
        Product.objects.annotate(
            supplier_label=Coalesce("supplier_ref__name", "supplier")
        )
        .values("supplier_label")
        .annotate(count=Count("id"))
        .order_by("supplier_label")
    )
    counts_map = {
        supplier_choice_map.get(item["supplier_label"], item["supplier_label"]): item["count"]
        for item in supplier_data
    }
    # Ensure Suppliers with no products still show up with zero
    for name in Supplier.objects.values_list("name", flat=True):
        counts_map.setdefault(name, 0)

    supplier_labels = list(counts_map.keys())
    supplier_values = list(counts_map.values())

    # 3. Recent Withdrawals Trend (last 30 days)
    today = now().date()
    start_date = today - datetime.timedelta(days=30)
    withdrawals = Withdrawal.objects.filter(timestamp__date__gte=start_date)
    withdrawal_by_day = withdrawals.extra({'day': "date(timestamp)"}).values('day').annotate(total=Count('id')).order_by('day')
    withdrawal_dates = [item['day'] for item in withdrawal_by_day]
    withdrawal_counts = [item['total'] for item in withdrawal_by_day]

    # 4. Top Withdrawn Products
    top_withdrawn = Withdrawal.objects.values('product_name').annotate(total=Sum('quantity')).order_by('-total')[:5]
    top_products_labels = [item['product_name'] for item in top_withdrawn]
    top_products_counts = [float(item['total']) for item in top_withdrawn]

    # 5. Stock by Location
    location_totals = {}
    products_with_location = Product.objects.select_related("location").prefetch_related("items")
    for product in products_with_location:
        loc_name = product.location.name if product.location else "Unassigned"
        total_stock = float(sum(item.current_stock for item in product.items.all()))
        location_totals[loc_name] = location_totals.get(loc_name, 0) + total_stock

    # If location tracking module is enabled, use detailed location stock
    try:
        from solutions.location_tracking.models import LocationStock

        location_stock_rows = LocationStock.objects.select_related("location", "product_item", "product_item__product")
        for row in location_stock_rows:
            loc_name = row.location.name if row.location else "Unassigned"
            location_totals[loc_name] = location_totals.get(loc_name, 0) + float(row.quantity)
    except Exception:
        pass

    # Ensure all locations appear, even with zero tracked stock
    for name in Location.objects.values_list("name", flat=True):
        location_totals.setdefault(name, 0)

    location_labels = list(location_totals.keys())
    location_values = list(location_totals.values())

    # 6. Expiring Soon Table
    today_plus_15 = int((today + datetime.timedelta(days=15)).strftime("%s"))
    today_plus_30 = int((today + datetime.timedelta(days=30)).strftime("%s"))

    expiring_soon = ProductItem.objects.filter(
        expiry_date__range=[today, today + datetime.timedelta(days=60)]
    ).order_by('expiry_date')

    return {
        'stock_labels': stock_labels,
        'stock_values': stock_values,
        'threshold_values': threshold_values,
        'stock_names': stock_names,
        'supplier_labels': supplier_labels,
        'supplier_values': supplier_values,
        'withdrawal_dates': withdrawal_dates,
        'withdrawal_counts': withdrawal_counts,
        'top_products_labels': top_products_labels,
        'top_products_counts': top_products_counts,
        'location_labels': location_labels,
        'location_values': location_values,
        'expiring_soon': expiring_soon,
        'today_plus_15': today_plus_15,
        'today_plus_30': today_plus_30,
    }



# import json
# import pandas as pd
# from datetime import timedelta
# from django.utils.timezone import now
# from django.shortcuts import render
# from django.db.models import Sum

# from statsmodels.tsa.holtwinters import ExponentialSmoothing

# from .models import Product, Withdrawal


def inventory_analysis_forecasting(request):
    # === Get Filter Parameters from GET ===
    selected_range = request.GET.get("range", "30")  # default: 1 month
    selected_limit = request.GET.get("limit", "all")  # default: all items

    try:
        days_back = int(selected_range)
    except ValueError:
        days_back = 30

    try:
        limit = None if selected_limit == "all" else int(selected_limit)
    except ValueError:
        limit = None

    # === Prepare Date Range ===
    today = now().date()
    start_date = today - timedelta(days=days_back)
    recent_dates = [start_date + timedelta(days=i) for i in range((today - start_date).days + 1)]

    # === Filtered Products ===
    products = Product.objects.prefetch_related('items').all()
    if limit:
        products = products[:limit]

    product_names = [p.name for p in products]
    current_stock = [float(sum(i.current_stock for i in p.items.all())) for p in products]
    stock_thresholds = [p.threshold for p in products]
    lead_times = [p.lead_time.days for p in products]

    # === Withdrawals over Date Range ===
    withdrawal_counts = [
        float(Withdrawal.objects.filter(timestamp__date=day).aggregate(total=Sum('quantity'))['total'] or 0)
        for day in recent_dates
    ]
    date_labels = [day.strftime("%b %d") for day in recent_dates]

    # === DataFrame for SMA & Forecast ===
    df = pd.DataFrame({"date": recent_dates, "withdrawals": withdrawal_counts}).set_index("date").asfreq("D", fill_value=0)
    df["withdrawals"] = pd.to_numeric(df["withdrawals"], errors="coerce").fillna(0)
    df["SMA_7"] = df["withdrawals"].rolling(window=7, min_periods=1).mean()
    df["SMA_14"] = df["withdrawals"].rolling(window=14, min_periods=1).mean()

    # === Exponential Smoothing Forecast ===
    forecast_values = [0] * 7
    if df["withdrawals"].sum() > 0:
        model = ExponentialSmoothing(df["withdrawals"], trend="add", seasonal=None, damped_trend=True)
        fitted = model.fit()
        forecast_values = [round(val, 2) for val in fitted.forecast(7).tolist()]

    forecast_dates = [(today + timedelta(days=i)).strftime("%b %d") for i in range(1, 8)]

    # === Run-Out & Reorder Estimates ===
    days_until_run_out = []
    days_until_reorder = []

    for idx, product in enumerate(products):
        total_withdrawn = Withdrawal.objects.filter(
            product_item__product=product,
            timestamp__gte=start_date
        ).aggregate(total=Sum('quantity'))['total'] or 0

        avg_daily = float(total_withdrawn) / max(days_back, 1)
        current = current_stock[idx]

        if avg_daily > 0 and current > 0:
            run_out = round(current / float(avg_daily), 2)
            reorder = max(run_out - lead_times[idx], 0)
        else:
            run_out = 0
            reorder = 0

        days_until_run_out.append(run_out)
        days_until_reorder.append(reorder)

    # === Top Consumed Products ===
    top = (Withdrawal.objects
           .filter(timestamp__date__gte=start_date)
           .values('product_name')
           .annotate(total_quantity=Sum('quantity'))
           .order_by('-total_quantity'))

    if limit:
        top = top[:limit]

    top_consumed_names = [i['product_name'] for i in top]
    top_consumed_quantities = [float(i['total_quantity']) for i in top]

    # === Final Context ===
    context = {
        "product_names": json.dumps(product_names),
        "current_stock": json.dumps(current_stock),
        "stock_thresholds": json.dumps(stock_thresholds),
        "date_labels": json.dumps(date_labels),
        "withdrawal_counts": json.dumps(withdrawal_counts),
        "sma_7": json.dumps(df["SMA_7"].fillna(0).tolist()),
        "sma_14": json.dumps(df["SMA_14"].fillna(0).tolist()),
        "forecast_dates": json.dumps(forecast_dates),
        "forecast_values": json.dumps(forecast_values),
        "lead_times": json.dumps(lead_times),
        "run_out_days": json.dumps(days_until_run_out),
        "reorder_days": json.dumps(days_until_reorder),
        "top_consumed_names": json.dumps(top_consumed_names),
        "top_consumed_quantities": json.dumps(top_consumed_quantities),
        "selected_range": selected_range,
        "selected_limit": selected_limit,
    }

    return render(request, 'analytics/inventory_analysis_forecasting.html', context)
