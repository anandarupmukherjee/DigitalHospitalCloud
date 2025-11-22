from django.urls import path

from . import views

app_name = "location_tracking"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("add/", views.add_stock, name="add_stock"),
    path("transfer/", views.transfer_stock, name="transfer_stock"),
    path("users/", views.manage_user_locations, name="user_locations"),
    path("stock-info/", views.location_stock_snapshot, name="location_stock_info"),
]
