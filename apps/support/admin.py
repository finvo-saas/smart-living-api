from django.contrib import admin

from core.admin import TimestampedModelAdmin
from support.models import Complaint, Dispute


@admin.register(Complaint)
class ComplaintAdmin(TimestampedModelAdmin):
    list_display = ('title', 'status', 'user', 'user_name')
    list_filter = ('status',)
    search_fields = ('title', 'user__phone', 'user_name')


@admin.register(Dispute)
class DisputeAdmin(TimestampedModelAdmin):
    list_display = ('title', 'status', 'complaint')
    list_filter = ('status',)
    search_fields = ('title',)
