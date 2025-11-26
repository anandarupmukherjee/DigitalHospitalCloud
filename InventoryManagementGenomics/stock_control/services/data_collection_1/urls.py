# services/data_collection_1/urls.py
from django.urls import path
from .stock_admin import stock_admin, delete_lot

app_name = 'data_collection_1'

urlpatterns = [
    path('stock_admin/', stock_admin, name='stock_admin'),
    path('stock_admin/<int:product_id>/', stock_admin, name='stock_admin_edit'),
    path('delete_lot/<int:item_id>/', delete_lot, name='delete_lot'),
]


    