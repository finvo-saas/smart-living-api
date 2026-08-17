from django.urls import path

from audit.views import AuditLogCreateView

urlpatterns = [
    path('audit/logs/', AuditLogCreateView.as_view(), name='audit-log-create'),
]
