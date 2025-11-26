from django.urls import path
from services.reporting.reporting import download_report

urlpatterns = [
    path('download_report/', download_report, name='download_report'),
]
