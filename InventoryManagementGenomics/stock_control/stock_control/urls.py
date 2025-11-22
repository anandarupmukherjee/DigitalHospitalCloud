from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from .module_loader import load_enabled_modules

modules = load_enabled_modules()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="inventory:dashboard", permanent=False)),
    path("", include("inventory.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("data/", include(("services.data_collection.urls", "data"), namespace="data")),
    path("data2/", include("services.data_collection_2.urls", namespace="data_collection_2")),
    path("data3/", include("services.data_collection_3.urls", namespace="data_collection_3")),
    path("stock/", include(("services.data_collection_1.urls", "data_collection_1"), namespace="data_collection_1")),
]

if modules.get("purchase_orders", {}).get("enabled"):
    urlpatterns.append(
        path(
            "purchase-orders/",
            include(("solutions.purchase_orders.urls", "purchase_orders"), namespace="purchase_orders"),
        )
    )

if modules.get("quality_control", {}).get("enabled"):
    urlpatterns.append(
        path(
            "quality-control/",
            include(("solutions.quality_control.urls", "quality_control"), namespace="quality_control"),
        )
    )

if modules.get("analytics", {}).get("enabled"):
    urlpatterns.append(
        path(
            "analytics/",
            include(("solutions.analytics.urls", "analytics"), namespace="analytics"),
        )
    )

if modules.get("location_tracking", {}).get("enabled"):
    urlpatterns.append(
        path(
            "location-tracking/",
            include(("solutions.location_tracking.urls", "location_tracking"), namespace="location_tracking"),
        )
    )
