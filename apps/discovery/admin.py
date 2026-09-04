from django.contrib import admin

from discovery.models import HeartbeatPing


@admin.register(HeartbeatPing)
class HeartbeatPingAdmin(admin.ModelAdmin):
    list_display = (
        'target_name',
        'target_type',
        'owner',
        'status',
        'dry_run',
        'sent_at',
        'expires_at',
    )
    list_filter = ('status', 'target_type', 'dry_run')
    search_fields = ('token', 'target_name', 'owner__phone', 'owner__name')
    readonly_fields = ('token', 'sent_at', 'responded_at')
