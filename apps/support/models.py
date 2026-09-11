from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimestampedModel, UUIDModel
from core.scope import ScopeType


class ComplaintStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    IN_PROGRESS = 'in_progress', 'In Progress'
    RESOLVED = 'resolved', 'Resolved'


class ComplaintCategory(models.TextChoices):
    MAINTENANCE = 'maintenance', 'Maintenance'
    BILLING = 'billing', 'Billing'
    NOISE = 'noise', 'Noise'
    OTHER = 'other', 'Other'


class Complaint(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='complaints',
    )
    user_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=ComplaintStatus.choices,
        default=ComplaintStatus.OPEN,
    )
    category = models.CharField(
        max_length=20,
        choices=ComplaintCategory.choices,
        default=ComplaintCategory.MAINTENANCE,
    )
    image_url = models.URLField(blank=True, default='')
    response = models.TextField(blank=True, default='')
    resolved_at = models.DateTimeField(null=True, blank=True)
    # Shared polymorphic scope (mess | building | hotel)
    scope_type = models.CharField(
        max_length=20,
        choices=ScopeType.choices,
        blank=True,
        default='',
        db_index=True,
    )
    scope_id = models.UUIDField(null=True, blank=True, db_index=True)
    scope_name = models.CharField(max_length=255, blank=True, default='')
    target_id = models.UUIDField(
        null=True,
        blank=True,
        help_text='Optional Flat / seat / room UUID under the scope.',
    )
    target_label = models.CharField(max_length=80, blank=True, default='')
    # Legacy apartment FKs (kept in sync when scope_type=building)
    building = models.ForeignKey(
        'portfolio.Building',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
    )
    flat = models.ForeignKey(
        'portfolio.Flat',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
    )
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'support_complaint'
        ordering = ('-created_at',)

    def __str__(self):
        return self.title


class ComplaintMessage(UUIDModel, TimestampedModel):
    """Simple maintenance ticket thread (renter ↔ owner)."""

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='complaint_messages',
    )
    author_name = models.CharField(max_length=255, blank=True, default='')
    body = models.TextField()
    is_staff_reply = models.BooleanField(
        default=False,
        help_text='True when owner/admin posted the message.',
    )

    class Meta:
        db_table = 'support_complaint_message'
        ordering = ('created_at',)

    def save(self, *args, **kwargs):
        if self.author_id and not self.author_name:
            user = self.author
            self.author_name = user.name or f'User {user.phone[-4:]}'
        super().save(*args, **kwargs)


class Dispute(UUIDModel, TimestampedModel):
    """Optional stub for future dispute resolution."""

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='disputes',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, blank=True, default='open')
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'support_dispute'
