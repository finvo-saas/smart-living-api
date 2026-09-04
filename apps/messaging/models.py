from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


class MessageType(models.TextChoices):
    TEXT = 'text', 'Text'
    IMAGE = 'image', 'Image'
    FILE = 'file', 'File'
    SYSTEM = 'system', 'System'


class MessageStatus(models.TextChoices):
    SENDING = 'sending', 'Sending'
    SENT = 'sent', 'Sent'
    DELIVERED = 'delivered', 'Delivered'
    READ = 'read', 'Read'


class NotificationType(models.TextChoices):
    COMPLAINT = 'complaint', 'Complaint'
    BILL = 'bill', 'Bill'
    SYSTEM = 'system', 'System'
    HEARTBEAT = 'heartbeat', 'Heartbeat'
    PUSH = 'push', 'Push'
    OTHER = 'other', 'Other'


class Chat(UUIDModel, TimestampedModel):
    participant1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chats_as_p1',
    )
    participant2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chats_as_p2',
    )
    participant1_name = models.CharField(max_length=255)
    participant2_name = models.CharField(max_length=255)
    participant1_avatar = models.URLField(blank=True, default='')
    participant2_avatar = models.URLField(blank=True, default='')
    last_message = models.TextField(blank=True, default='')
    last_message_time = models.DateTimeField(null=True, blank=True)
    unread_count_p1 = models.PositiveIntegerField(default=0)
    unread_count_p2 = models.PositiveIntegerField(default=0)
    property_id = models.UUIDField(null=True, blank=True, db_index=True)
    property_name = models.CharField(max_length=255, blank=True, default='')
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'messaging_chat'
        ordering = ('-last_message_time', '-updated_at')
        indexes = [
            models.Index(fields=['participant1', 'participant2']),
        ]

    def other_participant(self, user):
        if self.participant1_id == user.id:
            return self.participant2
        return self.participant1

    def unread_for(self, user):
        if self.participant1_id == user.id:
            return self.unread_count_p1
        return self.unread_count_p2


class ChatMessage(UUIDModel, TimestampedModel):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_chat_messages',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_chat_messages',
    )
    type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
    )
    content = models.TextField()
    file_name = models.CharField(max_length=255, blank=True, default='')
    file_size = models.PositiveIntegerField(null=True, blank=True)
    thumbnail = models.URLField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=MessageStatus.choices,
        default=MessageStatus.SENT,
    )
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'messaging_chat_message'
        ordering = ('created_at',)


class Notification(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.OTHER,
    )
    read = models.BooleanField(default=False)
    link = models.URLField(blank=True, default='')

    class Meta:
        db_table = 'messaging_notification'
        ordering = ('-created_at',)


class PushSubscription(UUIDModel, TimestampedModel):
    """Browser Web Push subscription (VAPID)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=200)
    user_agent = models.CharField(max_length=300, blank=True, default='')
    last_seen_at = models.DateTimeField(null=True, blank=True)
    fail_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'messaging_push_subscription'
        ordering = ('-updated_at',)

    def __str__(self):
        return f'{self.user_id}:{self.endpoint[-24:]}'
