from django.urls import path

from . import views

app_name = "purchase_orders"

urlpatterns = [
    path("record/", views.record_purchase_order, name="record_purchase_order"),
    path("track/", views.track_purchase_orders, name="track_purchase_orders"),
    path(
        "mark-delivered/<int:order_id>/",
        views.mark_order_delivered,
        name="mark_order_delivered",
    ),
]
