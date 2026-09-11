from django.conf import settings
from django.db import models
from django.db.models import Avg, Count
from django.utils import timezone

from core.models import TimestampedModel, UUIDModel
from core.services.media import upload_to_listing_image


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


class PropertyFace(models.TextChoices):
    NORTH = 'north', 'North'
    SOUTH = 'south', 'South'
    EAST = 'east', 'East'
    WEST = 'west', 'West'
    NORTH_EAST = 'north-east', 'North-East'
    NORTH_WEST = 'north-west', 'North-West'
    SOUTH_EAST = 'south-east', 'South-East'
    SOUTH_WEST = 'south-west', 'South-West'


class TenantType(models.TextChoices):
    FAMILY = 'family', 'Family'
    BACHELOR = 'bachelor', 'Bachelor'
    OFFICE = 'office', 'Office'
    ANY = 'any', 'Any'


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
    bedrooms = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='BHK / bedroom count for apartment listings.',
    )
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    kitchens = models.PositiveSmallIntegerField(null=True, blank=True)
    living_rooms = models.PositiveSmallIntegerField(null=True, blank=True)
    balconies = models.PositiveSmallIntegerField(null=True, blank=True)
    size_sqft = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Built-up size in square feet (not neighbourhood area).',
    )
    unit_number = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='Flat / unit number shown on public listing (e.g. A-5).',
    )
    property_face = models.CharField(
        max_length=20,
        choices=PropertyFace.choices,
        null=True,
        blank=True,
        help_text='Primary facing direction (Bproperty-style overview).',
    )
    service_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Monthly service charge in BDT (in addition to rent).',
    )
    parking_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Number of parking spaces included.',
    )
    available_from = models.DateField(
        null=True,
        blank=True,
        help_text='Move-in / availability date.',
    )
    rent_negotiable = models.BooleanField(
        default=False,
        help_text='Whether advertised rent is negotiable.',
    )
    tenant_type = models.CharField(
        max_length=20,
        choices=TenantType.choices,
        null=True,
        blank=True,
        help_text='Preferred occupancy: family, bachelor, office, or any.',
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
    address_verified = models.BooleanField(
        default=False,
        help_text='Team confirmed the address / map pin matches the premises.',
    )
    photos_verified = models.BooleanField(
        default=False,
        help_text='Team confirmed listing photos match the actual property.',
    )
    rent_verified = models.BooleanField(
        default=False,
        help_text='Team confirmed the advertised rent against owner docs / receipts.',
    )
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
    last_confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    flagged_unavailable_at = models.DateTimeField(null=True, blank=True)
    open_seats = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Live seat count synced from mess ops when linked.',
    )
    tour_images = models.JSONField(
        default=list,
        blank=True,
        help_text='360° panorama image URLs for virtual tour.',
    )
    cctv = models.BooleanField(null=True, blank=True)
    street_lighting = models.BooleanField(null=True, blank=True)

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
    file = models.ImageField(
        upload_to=upload_to_listing_image,
        null=True,
        blank=True,
    )
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
            from core.services.media import media_storage

            return media_storage.absolute_url(self.file.url, request=request)
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
    cleanliness = models.PositiveSmallIntegerField(null=True, blank=True)
    security = models.PositiveSmallIntegerField(null=True, blank=True)
    owner_behaviour = models.PositiveSmallIntegerField(null=True, blank=True)
    location = models.PositiveSmallIntegerField(null=True, blank=True)
    value_for_money = models.PositiveSmallIntegerField(null=True, blank=True)
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
