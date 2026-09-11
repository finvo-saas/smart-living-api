from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel
from core.scope import ScopeType


class NoticePriority(models.TextChoices):
    HIGH = 'high', 'High'
    MEDIUM = 'medium', 'Medium'
    LOW = 'low', 'Low'


class NoticeCategory(models.TextChoices):
    GENERAL = 'general', 'General'
    PAYMENT = 'payment', 'Payment'
    MAINTENANCE = 'maintenance', 'Maintenance'
    EVENT = 'event', 'Event'
    ANNOUNCEMENT = 'announcement', 'Announcement'
    RULE = 'rule', 'Rule'
    OTHER = 'other', 'Other'


class Notice(UUIDModel, TimestampedModel):
    """
    Unified building / mess / hotel notice (replaces MessNotice + BuildingNotice).

    scope_type + scope_id point at Mess | Building | Hotel.
    target_ids: optional child targeting (flat UUIDs for buildings; empty = all).
    """

    scope_type = models.CharField(max_length=20, choices=ScopeType.choices, db_index=True)
    scope_id = models.UUIDField(db_index=True)
    scope_name = models.CharField(max_length=255, blank=True, default='')
    target_ids = models.JSONField(
        default=list,
        blank=True,
        help_text='Empty = all units under scope; else Flat (or future seat) UUIDs.',
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    date = models.DateField()
    priority = models.CharField(max_length=10, choices=NoticePriority.choices)
    category = models.CharField(
        max_length=20,
        choices=NoticeCategory.choices,
        default=NoticeCategory.GENERAL,
    )
    expiry_date = models.DateField(null=True, blank=True)
    pdf_url = models.URLField(blank=True, default='')
    image_urls = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ops_notices_created',
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'ops_notice'
        ordering = ('-date', '-created_at')
        indexes = [
            models.Index(fields=['scope_type', 'scope_id', 'is_deleted']),
        ]

    def __str__(self):
        return f'{self.scope_type}:{self.scope_name or self.scope_id} — {self.title}'


class NoticeAck(UUIDModel, TimestampedModel):
    notice = models.ForeignKey(
        Notice,
        on_delete=models.CASCADE,
        related_name='acknowledgments',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ops_notice_acks',
    )
    user_name = models.CharField(max_length=255, blank=True, default='')
    acknowledged_at = models.DateTimeField()

    class Meta:
        db_table = 'ops_notice_ack'
        constraints = [
            models.UniqueConstraint(
                fields=['notice', 'user'],
                name='unique_ops_notice_ack_per_user',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.user_id and not self.user_name:
            user = self.user
            self.user_name = user.name or f'User {user.phone[-4:]}'
        super().save(*args, **kwargs)
