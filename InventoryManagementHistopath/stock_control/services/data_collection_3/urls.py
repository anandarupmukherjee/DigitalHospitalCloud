from django.urls import path
from .register_stock import register_stock

app_name = "data_collection_3"

urlpatterns = [
    path("register_stock/", register_stock, name="register_stock"),
]
