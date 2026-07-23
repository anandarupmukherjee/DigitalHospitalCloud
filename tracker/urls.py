from django.urls import path

from .views import (
    ConfigureTraysView,
    DashboardView,
    SystemAdminView,
    SystemMetricsDataView,
    TrayHeartbeatLogDownloadView,
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
    path('trays/<int:pk>/heartbeat-logs/', TrayHeartbeatLogDownloadView.as_view(), name='tray-heartbeat-log-download'),
    path('trays/configure/', ConfigureTraysView.as_view(), name='configure-trays'),
    path('topics/manage/', TopicManagementView.as_view(), name='topic-management'),
    path('users/manage/', UserManagementView.as_view(), name='user-management'),
    path('system/', SystemAdminView.as_view(), name='system-admin'),
    path('api/tray-status/', TrayStatusDataView.as_view(), name='tray-status-api'),
    path('api/system-metrics/', SystemMetricsDataView.as_view(), name='system-metrics-api'),
]
