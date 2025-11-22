from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("track-withdrawals/", views.track_withdrawals, name="track_withdrawals"),
    path("track-low-lots/", views.track_low_lots, name="track_low_lots"),
    path("track-expired-lots/", views.track_expired_lots, name="track_expired_lots"),
    path(
        "forecasting/",
        views.inventory_analysis_forecasting,
        name="inventory_analysis_forecasting",
    ),
    path("reports/download/", views.download_report, name="download_report"),
    path("intelligence/", views.intelligence, name="intelligence"),
]
