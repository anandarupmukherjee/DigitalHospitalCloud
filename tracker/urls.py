from django.urls import path

from .views import (
    ConfigureTraysView,
    DashboardView,
    TopicManagementView,
    TrayHistoryView,
    TrayReportDownloadView,
    TrayStatusDataView,
    UserManagementView,
)

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('trays/history/', TrayHistoryView.as_view(), name='tray-history'),
    path('trays/<int:pk>/report/', TrayReportDownloadView.as_view(), name='tray-report-download'),
    path('trays/configure/', ConfigureTraysView.as_view(), name='configure-trays'),
    path('topics/manage/', TopicManagementView.as_view(), name='topic-management'),
    path('users/manage/', UserManagementView.as_view(), name='user-management'),
    path('api/tray-status/', TrayStatusDataView.as_view(), name='tray-status-api'),
]
