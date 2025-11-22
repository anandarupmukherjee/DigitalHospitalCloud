from django.urls import path
from services.analysis.analysis import inventory_analysis_forecasting

urlpatterns = [
    path("analysis_forecasting/", inventory_analysis_forecasting, name="inventory_analysis_forecasting"),
    # path("forecasting/", inventory_forecasting, name="inventory_analysis"),
]
