from django.conf import settings
from django.db import models
from django.db.models import Avg, Count

from core.models import TimestampedModel, UUIDModel


DEFAULT_PRICING_RULES = {
    'weekendMultiplier': 1.15,
    'serviceChargePercent': 10,
    'vatPercent': 15,
    'seasonalRules': [],
}

DEFAULT_CANCELLATION = {
    'freeCancellationHours': 48,
    'partialRefundHours': 24,
    'partialRefundPercent': 50,
    'noRefundWithinHours': 24,
    'summary': (
        'Free cancellation up to 48 hours before check-in. '
        '50% refund between 48–24 hours. No refund within 24 hours of check-in.'
    ),
}


class HotelType(models.TextChoices):
    HOTEL = 'hotel', 'Hotel'
    GUEST_HOUSE = 'guest-house', 'Guest House'
    RESORT = 'resort', 'Resort'


class RoomType(models.TextChoices):
    SINGLE = 'single', 'Single'
    DOUBLE = 'double', 'Double'
    SUITE = 'suite', 'Suite'
    FAMILY = 'family', 'Family'


class HotelBookingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'
    CHECKED_IN = 'checked-in', 'Checked In'
    CHECKED_OUT = 'checked-out', 'Checked Out'


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    REFUNDED = 'refunded', 'Refunded'
    PARTIAL = 'partial', 'Partial'


class PaymentMethod(models.TextChoices):
    BKASH = 'bkash', 'bKash'
    NAGAD = 'nagad', 'Nagad'
    ROCKET = 'rocket', 'Rocket'
    CARD = 'card', 'Card'
    CASH = 'cash', 'Cash'


class Hotel(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hotels',
    )
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=HotelType.choices)
    star_rating = models.PositiveSmallIntegerField(null=True, blank=True)

    owner_name = models.CharField(max_length=255, blank=True, default='')
    owner_phone = models.CharField(max_length=20, blank=True, default='')
    owner_email = models.EmailField(blank=True, default='')

    address = models.CharField(max_length=255)
    area = models.CharField(max_length=120, db_index=True)
    city = models.CharField(max_length=80, db_index=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    images = models.JSONField(default=list, blank=True)
    description = models.TextField()
    amenities = models.JSONField(default=list, blank=True)

    check_in_time = models.CharField(max_length=5, default='14:00')
    check_out_time = models.CharField(max_length=5, default='12:00')
    minimum_stay = models.PositiveSmallIntegerField(default=1)

    license_number = models.CharField(max_length=64, blank=True, default='')
    license_document = models.URLField(blank=True, default='')

    verified = models.BooleanField(default=False, db_index=True)
    featured = models.BooleanField(default=False, db_index=True)

    average_rating = models.FloatField(default=0)
    total_reviews = models.PositiveIntegerField(default=0)

    total_rooms = models.PositiveIntegerField(default=0)
    available_rooms = models.PositiveIntegerField(default=0)

    cancellation_policy = models.JSONField(default=dict, blank=True)
    pricing_rules = models.JSONField(default=dict, blank=True)
    advance_payment_percent = models.PositiveSmallIntegerField(default=30)

    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'hotels_hotel'
        ordering = ('-featured', '-average_rating', '-created_at')
        indexes = [
            models.Index(fields=['city', 'area']),
            models.Index(fields=['type', 'verified']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.owner_id and not self.owner_name:
            owner = self.owner
            self.owner_name = owner.name or f'User {owner.phone[-4:]}'
            self.owner_phone = owner.phone
            self.owner_email = owner.email or ''
        if not self.cancellation_policy:
            self.cancellation_policy = dict(DEFAULT_CANCELLATION)
        if not self.pricing_rules:
            self.pricing_rules = dict(DEFAULT_PRICING_RULES)
        super().save(*args, **kwargs)

    def refresh_room_counts(self):
        rooms = self.rooms.all()
        self.total_rooms = rooms.count()
        self.available_rooms = rooms.filter(available=True).count()
        self.save(update_fields=['total_rooms', 'available_rooms', 'updated_at'])

    def refresh_rating_cache(self):
        agg = self.reviews.aggregate(avg=Avg('rating'), cnt=Count('id'))
        self.average_rating = round(float(agg['avg'] or 0), 2)
        self.total_reviews = agg['cnt'] or 0
        self.save(update_fields=['average_rating', 'total_reviews', 'updated_at'])


class Room(UUIDModel, TimestampedModel):
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='rooms',
    )
    room_number = models.CharField(max_length=32)
    type = models.CharField(max_length=20, choices=RoomType.choices)
    floor = models.PositiveSmallIntegerField(default=1)
    capacity = models.PositiveSmallIntegerField(default=2)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    amenities = models.JSONField(default=list, blank=True)
    images = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default='')
    available = models.BooleanField(default=True)

    class Meta:
        db_table = 'hotels_room'
        ordering = ('floor', 'room_number')
        constraints = [
            models.UniqueConstraint(
                fields=['hotel', 'room_number'],
                name='unique_room_number_per_hotel',
            ),
        ]

    def __str__(self):
        return f'{self.hotel.name} — {self.room_number}'


class RoomPrice(UUIDModel, TimestampedModel):
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='prices',
    )
    date = models.DateField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_weekend = models.BooleanField(default=False)
    is_special_offer = models.BooleanField(default=False)
    offer_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'hotels_room_price'
        ordering = ('date',)
        constraints = [
            models.UniqueConstraint(
                fields=['room', 'date'],
                name='unique_room_price_per_date',
            ),
        ]


class HotelBooking(UUIDModel, TimestampedModel):
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hotel_bookings',
    )

    guest_name = models.CharField(max_length=255)
    guest_phone = models.CharField(max_length=20)
    guest_email = models.EmailField(blank=True, default='')

    check_in = models.DateField()
    check_out = models.DateField()
    check_in_time = models.CharField(max_length=5, blank=True, default='')
    check_out_time = models.CharField(max_length=5, blank=True, default='')

    guests = models.PositiveSmallIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=HotelBookingStatus.choices,
        default=HotelBookingStatus.PENDING,
        db_index=True,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    advance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
        default='',
    )
    transaction_id = models.CharField(max_length=128, blank=True, default='')

    special_requests = models.TextField(blank=True, default='')
    fee_breakdown = models.JSONField(default=dict, blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    cancellation_note = models.TextField(blank=True, default='')

    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'hotels_hotel_booking'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['hotel', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['room', 'check_in', 'check_out']),
        ]


class HotelReview(UUIDModel, TimestampedModel):
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    booking = models.ForeignKey(
        HotelBooking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hotel_reviews',
    )

    user_name = models.CharField(max_length=255, blank=True, default='')
    user_avatar = models.URLField(blank=True, default='')

    rating = models.PositiveSmallIntegerField()
    comment = models.TextField()
    images = models.JSONField(default=list, blank=True)

    owner_response = models.TextField(blank=True, default='')
    owner_response_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'hotels_hotel_review'
        ordering = ('-created_at',)

    def save(self, *args, **kwargs):
        if self.user_id and not self.user_name:
            user = self.user
            self.user_name = user.name or f'User {user.phone[-4:]}'
            if user.profile_photo:
                self.user_avatar = user.profile_photo.url
        super().save(*args, **kwargs)
