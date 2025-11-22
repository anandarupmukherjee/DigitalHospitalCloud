# urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


app_name = 'inventory'

urlpatterns = [
    # Dashboard
    # path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/', views.inventory_dashboard, name='dashboard'),
    
    # Stock Admin: no product_id => list/add, with product_id => edit
    # path('stock_admin/', views.stock_admin, name='stock_admin'),
    # path('stock_admin/<int:product_id>/', views.stock_admin, name='stock_admin_edit'),
    # path('delete_lot/<int:item_id>/', views.delete_lot, name='delete_lot'),

    
    # Create Withdrawal / Product List
    # path('create_withdrawal/', views.create_withdrawal, name='create_withdrawal'),
    path('product_list/', views.product_list, name='product_list'),
    # path('get-product-by-id/', views.get_product_by_id, name='get_product_by_id'),


    # AJAX
    # path('data/get-product-by-barcode/', views.get_product_by_barcode, name='get_product_by_barcode'),
    # path('data/get-product-by-id/', views.get_product_by_id, name='get_product_by_id'),
    # path("data/parse-barcode/", views.parse_barcode, name="parse_barcode"),

    
    # Tracking & Purchase Orders
    # path('complete_purchase_order/', views.complete_purchase_order, name='complete_purchase_order'),


    # Reports
    # path('download_report/', views.download_report, name='download_report'),
    # path('export/', views.export_data_view, name='export_data'),
    # path("analysis_forecasting/", views.inventory_analysis_forecasting, name="inventory_analysis_forecasting"),

    # path("forecasting/", views.inventory_forecasting, name="inventory_analysis"),



    # Admin user management
    path('manage_users/', views.manage_users, name='manage_users'),
    path('register_user/', views.register_user, name='register_user'),
    path('edit_user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete_user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('manage_suppliers/', views.manage_suppliers, name='manage_suppliers'),
    path('import/', views.import_inventory, name='import_inventory'),
    path('suppliers/<int:supplier_id>/products/', views.supplier_products, name='supplier_products'),
    path('manage_locations/', views.manage_locations, name='manage_locations'),
    path('locations/<int:location_id>/products/', views.location_products, name='location_products'),
    path('manage_product_codes/', views.manage_product_codes, name='manage_product_codes'),
    path('help/', views.help_page, name='help'),

    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
]
