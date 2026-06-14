import csv
import datetime
import io

from django.core.paginator import Paginator
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timezone import make_aware, now
from openpyxl import Workbook

from services.data_storage.models import Product, ProductItem, StockRegistration, Withdrawal

try:
    from solutions.quality_control.models import QualityCheck
except Exception:
    QualityCheck = None


REPORT_COLUMNS = [
    ("registration_date", "Date (Registration)"),
    ("product_name", "Product"),
    ("product_code", "Product Code"),
    ("lot_number", "Lot Number"),
    ("expiry_date", "Expire Date"),
    ("quantity", "Quantity"),
    ("items_in_stock", "No. of Products in Stock"),
    ("location_name", "Location"),
    ("registered_by", "User (Registered)"),
    ("withdrawn_by", "User (Withdraw)"),
    ("withdrawal_date", "Date Withdraw"),
    ("qc_status", "QC Status"),
    ("qc_by", "Person QC'ed"),
    ("qc_date", "Date QC'ed"),
]

PRODUCT_SUMMARY_COLUMNS = [
    ("product_name", "Product"),
    ("product_code", "Product Code"),
    ("items_in_stock", "Items In Stock"),
    ("expired_lots", "Expired Lots"),
]


def _parse_date(value, end_of_day=False):
    if not value:
        return None
    parsed = datetime.datetime.strptime(value, "%Y-%m-%d")
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return make_aware(parsed)


def _base_queryset(start_date, end_date):
    qs = StockRegistration.objects.select_related(
        "product_item",
        "product_item__product",
        "product_item__product__location",
        "location",
        "user",
    ).order_by("-timestamp", "-id")

    if start_date:
        qs = qs.filter(timestamp__gte=_parse_date(start_date))
    if end_date:
        qs = qs.filter(timestamp__lte=_parse_date(end_date, end_of_day=True))

    latest_withdrawal = Withdrawal.objects.filter(
        product_item_id=OuterRef("product_item_id")
    ).order_by("-timestamp", "-id")
    qs = qs.annotate(
        latest_withdrawal_user=Subquery(latest_withdrawal.values("user__username")[:1]),
        latest_withdrawal_timestamp=Subquery(latest_withdrawal.values("timestamp")[:1]),
    )

    available_stock = (
        ProductItem.objects.filter(
            product_id=OuterRef("product_item__product_id"),
            expiry_date__gt=timezone.localdate(),
        )
        .values("product_id")
        .annotate(
            total=Coalesce(
                Sum("current_stock"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .values("total")[:1]
    )
    qs = qs.annotate(
        product_items_in_stock=Coalesce(
            Subquery(available_stock, output_field=DecimalField(max_digits=12, decimal_places=2)),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )

    if QualityCheck is not None:
        latest_qc = QualityCheck.objects.filter(
            product_item_id=OuterRef("product_item_id")
        ).order_by("-created_at", "-id")
        qs = qs.annotate(
            latest_qc_result=Subquery(latest_qc.values("result")[:1]),
            latest_qc_user=Subquery(latest_qc.values("performed_by__username")[:1]),
            latest_qc_timestamp=Subquery(latest_qc.values("created_at")[:1]),
        )
    return qs


def _row_from_registration(registration):
    product_item = registration.product_item
    product = getattr(product_item, "product", None) if product_item else None
    location_name = ""
    if registration.location:
        location_name = registration.location.name
    elif product and product.location:
        location_name = product.location.name

    latest_qc_result = getattr(registration, "latest_qc_result", None)
    qc_status = "Passed" if latest_qc_result == "pass" else "Waiting"

    return {
        "registration_date": registration.timestamp,
        "product_name": registration.product_name,
        "product_code": registration.product_code,
        "lot_number": registration.lot_number,
        "expiry_date": registration.expiry_date,
        "quantity": registration.quantity,
        "items_in_stock": getattr(registration, "product_items_in_stock", 0),
        "location_name": location_name,
        "registered_by": registration.user.username if registration.user else "",
        "withdrawn_by": getattr(registration, "latest_withdrawal_user", "") or "",
        "withdrawal_date": getattr(registration, "latest_withdrawal_timestamp", None),
        "qc_status": qc_status,
        "qc_by": getattr(registration, "latest_qc_user", "") or "",
        "qc_date": getattr(registration, "latest_qc_timestamp", None),
    }


def _format_value(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        return value.strftime("%Y-%m-%d")
    return str(value)


def _build_rows(queryset):
    return [_row_from_registration(registration) for registration in queryset]


def _build_product_summary_rows(queryset):
    product_ids = list(
        queryset.exclude(product_item__product_id__isnull=True)
        .values_list("product_item__product_id", flat=True)
        .distinct()
    )
    if not product_ids:
        return []

    products = Product.objects.filter(id__in=product_ids).prefetch_related("items").order_by("name")
    rows = []
    for product in products:
        expired_lots = [
            item.lot_number
            for item in product.items.all()
            if item.is_expired
        ]
        rows.append(
            {
                "product_name": product.name,
                "product_code": product.product_code or "",
                "items_in_stock": product.get_available_stock(),
                "expired_lots": ", ".join(expired_lots),
            }
        )
    return rows


def _download_response(rows, product_summary_rows, download_type, user_part, date_part):
    headers = [label for _, label in REPORT_COLUMNS]
    values = [[_format_value(row[key]) for key, _ in REPORT_COLUMNS] for row in rows]

    if download_type == "excel":
        wb = Workbook()
        ws = wb.active
        ws.title = "Inventory Report"
        ws.append(headers)
        for row in values:
            ws.append(row)

        summary_ws = wb.create_sheet(title="Product Summary")
        summary_headers = [label for _, label in PRODUCT_SUMMARY_COLUMNS]
        summary_ws.append(summary_headers)
        for row in product_summary_rows:
            summary_ws.append([_format_value(row[key]) for key, _ in PRODUCT_SUMMARY_COLUMNS])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        response = HttpResponse(
            out,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename=IMS_{user_part}_{date_part}.xlsx"
        return response

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(headers)
    for row in values:
        writer.writerow(row)
    response = HttpResponse(csv_buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=IMS_{user_part}_{date_part}.csv"
    return response


def download_report(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    download_type = request.GET.get("download")
    page_number = request.GET.get("page", 1)

    queryset = _base_queryset(start_date, end_date)

    if download_type in {"excel", "csv"}:
        rows = _build_rows(queryset)
        product_summary_rows = _build_product_summary_rows(queryset)
        user_part = request.user.username if request.user.is_authenticated else "anonymous"
        date_part = now().strftime("%Y%m%d")
        return _download_response(rows, product_summary_rows, download_type, user_part, date_part)

    paginator = Paginator(queryset, 100)
    page_obj = paginator.get_page(page_number)
    rows = _build_rows(page_obj.object_list)

    return render(
        request,
        "analytics/download_report.html",
        {
            "columns": REPORT_COLUMNS,
            "rows": rows,
            "page_obj": page_obj,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
