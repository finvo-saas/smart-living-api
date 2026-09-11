from django.contrib import admin

from core.admin import TimestampedModelAdmin
from messaging.models import Chat, ChatMessage, Notification, PushSubscription


@admin.register(Chat)
class ChatAdmin(TimestampedModelAdmin):
    list_display = (
        'participant1_name',
        'participant2_name',
        'property_name',
        'last_message_time',
        'is_deleted',
    )
    search_fields = ('participant1_name', 'participant2_name', 'property_name')


@admin.register(ChatMessage)
class ChatMessageAdmin(TimestampedModelAdmin):
    list_display = ('chat', 'sender', 'receiver', 'type', 'status')
    list_filter = ('type', 'status')
    search_fields = ('content', 'sender__phone', 'receiver__phone')


@admin.register(Notification)
class NotificationAdmin(TimestampedModelAdmin):
    list_display = ('user', 'title', 'type', 'read')
    list_filter = ('read', 'type')
    search_fields = ('title', 'user__phone')


@admin.register(PushSubscription)
class PushSubscriptionAdmin(TimestampedModelAdmin):
    list_display = ('user', 'endpoint', 'fail_count', 'last_seen_at')
    search_fields = ('user__phone', 'endpoint')
