from django.contrib import admin

from admin_api.models import (
    ActivityLog,
    Dispute,
    FraudReport,
    SystemSettings,
    UserModeration,
)
from core.admin import TimestampedModelAdmin


@admin.register(Dispute)
class AdminDisputeAdmin(TimestampedModelAdmin):
    list_display = ('title', 'status', 'priority', 'type')
    list_filter = ('status', 'priority', 'type')
    search_fields = ('title',)


@admin.register(FraudReport)
class FraudReportAdmin(TimestampedModelAdmin):
    list_display = ('report_type', 'status', 'user', 'user_name', 'priority')
    list_filter = ('report_type', 'status', 'priority')
    search_fields = ('user__phone', 'user_name')


@admin.register(ActivityLog)
class ActivityLogAdmin(TimestampedModelAdmin):
    list_display = ('action', 'resource_type', 'user', 'user_name')
    list_filter = ('resource_type',)
    search_fields = ('user__phone', 'user_name', 'resource_id')


@admin.register(UserModeration)
class UserModerationAdmin(TimestampedModelAdmin):
    list_display = ('user', 'status')
    list_filter = ('status',)
    search_fields = ('user__phone',)


@admin.register(SystemSettings)
class SystemSettingsAdmin(TimestampedModelAdmin):
    list_display = ('platform_name', 'platform_email', 'commission_rate')
