from django.contrib import admin

from audit.models import AuditLog
from core.admin import TimestampedModelAdmin


@admin.register(AuditLog)
class AuditLogAdmin(TimestampedModelAdmin):
    list_display = ('action', 'entity_type', 'entity_name', 'user', 'user_name')
    list_filter = ('action', 'entity_type')
    search_fields = ('user__phone', 'entity_id', 'entity_name')
