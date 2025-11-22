from django.urls import path

from . import views

app_name = "quality_control"

urlpatterns = [
    path("checks/", views.list_checks, name="list_checks"),
    path("lots/", views.lot_status, name="lot_status"),
    path("checks/create/", views.create_check, name="create_check"),
]
