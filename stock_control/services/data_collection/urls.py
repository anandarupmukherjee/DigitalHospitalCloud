from django.urls import path
from services.data_collection.data_collection import (
    create_barcode_mapping,
    product_dropdown,
    parse_barcode,
    get_product_by_barcode,
    get_product_by_id,
)

urlpatterns = [
    path('get-product-by-barcode/', get_product_by_barcode, name='get_product_by_barcode'),
    path('get-product-by-id/', get_product_by_id, name='get_product_by_id'),
    path('products/dropdown/', product_dropdown, name='product_dropdown'),
    path('barcode-mappings/create/', create_barcode_mapping, name='create_barcode_mapping'),
    path("parse-barcode/", parse_barcode, name="parse_barcode"),
]
