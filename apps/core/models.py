import uuid

from django.conf import settings
from django.db import models


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MediaVisibility(models.TextChoices):
    PUBLIC = 'public', 'Public'
    PRIVATE = 'private', 'Private'


class MediaAsset(UUIDModel, TimestampedModel):
    """Owner-scoped index of files stored in Spaces (or local storage).

    The object lives in the bucket. This row is how each owner browses and
    reuses their own uploads. Store ``storage_key`` — public URLs are derived
    today; a future private bucket can serve signed URLs from the same key.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='media_assets',
    )
    storage_key = models.CharField(max_length=512, unique=True, db_index=True)
    url = models.URLField(max_length=1000, blank=True, default='')
    kind = models.CharField(max_length=40, db_index=True)
    original_name = models.CharField(max_length=255, blank=True, default='')
    content_type = models.CharField(max_length=120, blank=True, default='')
    size_bytes = models.PositiveIntegerField(default=0)
    visibility = models.CharField(
        max_length=16,
        choices=MediaVisibility.choices,
        default=MediaVisibility.PUBLIC,
        db_index=True,
    )

    class Meta:
        db_table = 'core_media_asset'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['owner', 'kind', '-created_at']),
        ]

    def __str__(self):
        return self.original_name or self.storage_key
