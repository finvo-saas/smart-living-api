from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel
from listings.models import Property


class Favorite(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='favorited_by',
    )
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'discovery_favorite'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'property'],
                name='unique_favorite_user_property',
            ),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.property_id}'


class SavedSearch(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_searches',
    )
    name = models.CharField(max_length=120)
    filters = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    match_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'discovery_saved_search'
        ordering = ('-updated_at',)

    def __str__(self):
        return self.name


class SearchHistory(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='search_history',
    )
    search_query = models.CharField(max_length=255, blank=True, default='')
    filters = models.JSONField(default=dict)
    result_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'discovery_search_history'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user_id}:{self.created_at}'


class HeartbeatTargetType(models.TextChoices):
    LISTING = 'listing', 'Listing'
    HOTEL = 'hotel', 'Hotel'
    MESS = 'mess', 'Mess'


class HeartbeatStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    DRY_RUN = 'dry_run', 'Dry run'
    FAILED = 'failed', 'Failed'
    CONFIRMED = 'confirmed', 'Still available'
    MARKED_FULL = 'marked_full', 'Marked full'
    EXPIRED = 'expired', 'Expired'


class HeartbeatPing(UUIDModel, TimestampedModel):
    """One vacancy-confirm SMS/link sent to an owner for a live listing."""

    token = models.CharField(max_length=48, unique=True, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='heartbeat_pings',
    )
    target_type = models.CharField(
        max_length=20,
        choices=HeartbeatTargetType.choices,
        db_index=True,
    )
    target_id = models.UUIDField(db_index=True)
    target_name = models.CharField(max_length=255)
    target_city = models.CharField(max_length=80, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=HeartbeatStatus.choices,
        default=HeartbeatStatus.PENDING,
        db_index=True,
    )
    channel = models.CharField(max_length=20, default='sms')
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    sms_body = models.TextField(blank=True, default='')
    error_message = models.CharField(max_length=500, blank=True, default='')
    dry_run = models.BooleanField(default=False)

    class Meta:
        db_table = 'discovery_heartbeat_ping'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['owner', 'sent_at']),
            models.Index(fields=['target_type', 'target_id', '-created_at']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return f'{self.target_type}:{self.target_name}:{self.status}'
