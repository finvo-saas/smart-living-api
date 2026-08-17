from django.conf import settings
from django.db import models
from django.db.models import Avg, Count
from django.utils import timezone

from core.models import TimestampedModel, UUIDModel


class PropertyType(models.TextChoices):
    MESS = 'mess', 'Mess'
    APARTMENT = 'apartment', 'Apartment'
    HOSTEL = 'hostel', 'Hostel'
    HOTEL = 'hotel', 'Hotel'


class Gender(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'
    MIXED = 'mixed', 'Mixed'


class SeatType(models.TextChoices):
    SINGLE = 'single', 'Single'
    SHARED = 'shared', 'Shared'


class MealPlan(models.TextChoices):
    BREAKFAST = 'breakfast', 'Breakfast'
    LUNCH = 'lunch', 'Lunch'
    DINNER = 'dinner', 'Dinner'
    ALL = 'all', 'All'


class FurnishingStatus(models.TextChoices):
    FURNISHED = 'furnished', 'Furnished'
    UNFURNISHED = 'unfurnished', 'Unfurnished'
    SEMI = 'semi-furnished', 'Semi-furnished'


class VerificationStatus(models.TextChoices):
    VERIFIED = 'verified', 'Verified'
    PENDING = 'pending', 'Pending'
    UNVERIFIED = 'unverified', 'Unverified'


class ListingStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    PUBLISHED = 'published', 'Published'
    PAUSED = 'paused', 'Paused'
    REJECTED = 'rejected', 'Rejected'


class Property(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='properties',
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=PropertyType.choices)
    rent = models.DecimalField(max_digits=12, decimal_places=2)
    area = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80, db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    available = models.BooleanField(default=True)
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        null=True,
        blank=True,
    )
    seat_type = models.CharField(
        max_length=20,
        choices=SeatType.choices,
        null=True,
        blank=True,
    )
    meal_included = models.BooleanField(null=True, blank=True)
    meal_plan = models.CharField(
        max_length=20,
        choices=MealPlan.choices,
        null=True,
        blank=True,
    )
    meal_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # URL lists for Phase 2 (external/CDN); uploads attach via PropertyImage
    image_urls = models.JSONField(default=list, blank=True)
    videos = models.JSONField(default=list, blank=True)
    video_thumbnail = models.URLField(blank=True, default='')
    facilities = models.JSONField(default=list, blank=True)
    nearby_facilities = models.JSONField(default=list, blank=True)
    building_age = models.PositiveSmallIntegerField(null=True, blank=True)
    floor_level = models.PositiveSmallIntegerField(null=True, blank=True)
    furnishing = models.CharField(
        max_length=20,
        choices=FurnishingStatus.choices,
        null=True,
        blank=True,
    )
    parking = models.BooleanField(null=True, blank=True)
    security = models.BooleanField(null=True, blank=True)
    verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNVERIFIED,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField()
    instant_book = models.BooleanField(default=False)
    deposit_months = models.PositiveSmallIntegerField(default=1)
    published = models.BooleanField(default=False, db_index=True)
    listing_status = models.CharField(
        max_length=20,
        choices=ListingStatus.choices,
        default=ListingStatus.DRAFT,
        db_index=True,
    )
    rating = models.FloatField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False, db_index=True)
    featured_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'listings_property'
        ordering = ('-featured', '-created_at')
        indexes = [
            models.Index(fields=['city', 'area']),
            models.Index(fields=['type', 'published']),
            models.Index(fields=['rent']),
        ]

    def __str__(self):
        return self.name

    def refresh_rating_cache(self):
        agg = self.reviews.aggregate(avg=Avg('rating'), cnt=Count('id'))
        self.rating = round(float(agg['avg'] or 0), 2)
        self.review_count = agg['cnt'] or 0
        self.save(update_fields=['rating', 'review_count', 'updated_at'])

    @property
    def is_featured_active(self) -> bool:
        if not self.featured:
            return False
        if self.featured_until and self.featured_until < timezone.now():
            return False
        return True


class PropertyImage(UUIDModel, TimestampedModel):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='image_files',
    )
    file = models.ImageField(upload_to='listings/', null=True, blank=True)
    url = models.URLField(blank=True, default='')
    sort_order = models.PositiveSmallIntegerField(default=0)
    alt_text = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'listings_property_image'
        ordering = ('sort_order', 'created_at')

    def resolved_url(self, request=None) -> str:
        if self.url:
            return self.url
        if self.file:
            url = self.file.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return ''


class PropertyReview(UUIDModel, TimestampedModel):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='property_reviews',
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField()
    images = models.JSONField(default=list, blank=True)
    stay_duration_months = models.PositiveSmallIntegerField(null=True, blank=True)
    verified_stay = models.BooleanField(default=False)
    owner_response = models.TextField(blank=True, default='')
    owner_response_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'listings_property_review'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'user'],
                name='unique_review_per_user_property',
            ),
        ]

    def __str__(self):
        return f'{self.property_id}:{self.user_id}:{self.rating}'
