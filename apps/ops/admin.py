from django.contrib import admin

from core.admin import TimestampedModelAdmin
from ops.models import Notice, NoticeAck


@admin.register(Notice)
class NoticeAdmin(TimestampedModelAdmin):
    list_display = (
        'title',
        'scope_type',
        'scope_name',
        'priority',
        'date',
        'is_deleted',
    )
    list_filter = ('scope_type', 'priority', 'category', 'is_deleted')
    search_fields = ('title', 'scope_name', 'content')


@admin.register(NoticeAck)
class NoticeAckAdmin(TimestampedModelAdmin):
    list_display = ('notice', 'user_name', 'acknowledged_at')
    search_fields = ('user_name',)
