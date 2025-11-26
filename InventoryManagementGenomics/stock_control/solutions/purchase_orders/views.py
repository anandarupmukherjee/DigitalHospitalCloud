import datetime
import json

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import now

from inventory.access_control import group_required
from inventory.roles import ROLE_INVENTORY_MANAGER, user_is_inventory_manager
from services.data_collection.data_collection import parse_barcode as _parse_barcode
from services.data_storage.models import (
    Product,
    ProductItem,
    PurchaseOrder,
    PurchaseOrderCompletionLog,
)

from .forms import PurchaseOrderCompletionForm, PurchaseOrderForm


def is_admin(user):
    return user_is_inventory_manager(user)


@login_required
@user_passes_test(is_admin, login_url="inventory:dashboard")
def record_purchase_order(request):
    initial = {}
    if request.method == "GET":
        product_code = request.GET.get("product_code")
        product_name = request.GET.get("product_name")
        if product_code:
            initial["product_code"] = product_code
        if product_name:
            initial["product_name"] = product_name

    if request.method == "POST":
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            po = form.save(commit=False)
            po.ordered_by = request.user

            if not po.product_item and form.cleaned_data.get("product_code"):
                product_code = form.cleaned_data["product_code"]
                product = Product.objects.filter(product_code=product_code).first()
                if product:
                    product_item = (
                        ProductItem.objects.filter(product=product)
                        .order_by("expiry_date")
                        .first()
                    )
                    if product_item:
                        po.product_item = product_item
            po.save()

            if po.status == "Delivered" and po.product_item:
                po.product_item.current_stock = F("current_stock") + po.quantity_ordered
                po.product_item.save()

            return redirect("purchase_orders:record_purchase_order")
    else:
        form = PurchaseOrderForm(initial=initial)

    products = Product.objects.all()
    low_stock = []
    for product in products:
        total_stock = sum(item.current_stock for item in product.items.all())
        if total_stock < product.threshold:
            low_stock.append(product)

    return render(
        request,
        "purchase_orders/record_purchase_order.html",
        {"form": form, "low_stock": low_stock},
    )


@login_required
@group_required([ROLE_INVENTORY_MANAGER])
def track_purchase_orders(request):
    orders = PurchaseOrder.objects.select_related("product_item", "ordered_by").order_by(
        "-order_date"
    )
    for order in orders:
        if order.expected_delivery < now() and order.status == "Ordered":
            order.status = "Delayed"
            order.save()

    initial = {}
    if request.method == "GET" and "raw" in request.GET:
        raw = request.GET.get("raw", "")
        if raw:
            response = _parse_barcode(request)
            if response.status_code == 200:
                data = json.loads(response.content)
                product = Product.objects.filter(
                    product_code=data.get("product_code")
                ).first()
                initial.update(
                    {
                        "barcode": raw,
                        "product_code": data.get("product_code", ""),
                        "product_name": product.name if product else "",
                        "lot_number": data.get("lot_number", ""),
                        "expiry_date": datetime.datetime.strptime(
                            data.get("expiry_date", "01.01.1970"), "%d.%m.%Y"
                        ).date()
                        if data.get("expiry_date")
                        else None,
                    }
                )

    if request.method == "POST":
        form = PurchaseOrderCompletionForm(request.POST)
        if form.is_valid():
            barcode = form.cleaned_data["barcode"]
            product_code = form.cleaned_data["product_code"]
            product_name = form.cleaned_data["product_name"]
            lot_number = form.cleaned_data["lot_number"]
            expiry_date = form.cleaned_data["expiry_date"]
            qty = form.cleaned_data["quantity_ordered"]

            product = Product.objects.filter(product_code=product_code).first()
            if not product:
                form.add_error(None, "Product not found.")
                return render(
                    request,
                    "purchase_orders/track_purchase_orders.html",
                    {"purchase_orders": orders, "completion_form": form},
                )

            item, created = ProductItem.objects.get_or_create(
                product=product,
                lot_number=lot_number,
                expiry_date=expiry_date,
                defaults={"current_stock": 0},
            )

            item.current_stock = F("current_stock") + qty
            item.save()

            matching = PurchaseOrder.objects.filter(
                Q(product_item=item),
                Q(status="Ordered") | Q(status="Delayed"),
            ).first()

            if matching:
                matching.status = "Delivered"
                matching.delivered_at = timezone.now()
                matching.save()
                PurchaseOrderCompletionLog.objects.create(
                    purchase_order=matching,
                    product_code=matching.product_code,
                    product_name=matching.product_name,
                    lot_number=matching.lot_number,
                    expiry_date=matching.expiry_date,
                    quantity_ordered=matching.quantity_ordered,
                    order_date=matching.order_date,
                    ordered_by=matching.ordered_by,
                    completed_by=request.user,
                    remarks="Completed via form",
                )

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "product_code": product_code,
                        "status": "Delivered",
                    }
                )
            return redirect("purchase_orders:track_purchase_orders")

        return render(
            request,
            "purchase_orders/track_purchase_orders.html",
            {"purchase_orders": orders, "completion_form": form},
        )

    form = PurchaseOrderCompletionForm(initial=initial)
    return render(
        request,
        "purchase_orders/track_purchase_orders.html",
        {"purchase_orders": orders, "completion_form": form},
    )


@login_required
@user_passes_test(is_admin, login_url="inventory:dashboard")
def mark_order_delivered(request, order_id):
    purchase_order = get_object_or_404(PurchaseOrder, id=order_id)
    if purchase_order.status != "Delivered":
        if purchase_order.product_item:
            purchase_order.product_item.current_stock = (
                F("current_stock") + purchase_order.quantity_ordered
            )
            purchase_order.product_item.save()
        purchase_order.status = "Delivered"
        purchase_order.save()
    return redirect("purchase_orders:track_purchase_orders")
