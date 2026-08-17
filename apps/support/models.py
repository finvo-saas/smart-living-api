from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimestampedModel, UUIDModel


class ComplaintStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    IN_PROGRESS = 'in_progress', 'In Progress'
    RESOLVED = 'resolved', 'Resolved'


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
    image_url = models.URLField(blank=True, default='')
    response = models.TextField(blank=True, default='')
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'support_complaint'
        ordering = ('-created_at',)

    def __str__(self):
        return self.title


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
