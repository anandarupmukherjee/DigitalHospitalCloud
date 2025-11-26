from django.urls import path
from services.data_collection.data_collection import (
    parse_barcode,
    get_product_by_barcode,
    get_product_by_id,
)

urlpatterns = [
    path('get-product-by-barcode/', get_product_by_barcode, name='get_product_by_barcode'),
    path('get-product-by-id/', get_product_by_id, name='get_product_by_id'),
    path("parse-barcode/", parse_barcode, name="parse_barcode"),
]
