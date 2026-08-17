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
