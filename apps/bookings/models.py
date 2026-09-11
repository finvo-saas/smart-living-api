from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


class BookingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    CANCELLED = 'cancelled', 'Cancelled'
    COMPLETED = 'completed', 'Completed'


class BookingMode(models.TextChoices):
    INSTANT = 'instant', 'Instant'
    REQUEST = 'request', 'Request'


class PropertyBooking(UUIDModel, TimestampedModel):
    property = models.ForeignKey(
        'listings.Property',
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    renter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='property_bookings',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_property_bookings',
    )

    property_name = models.CharField(max_length=255)
    property_type = models.CharField(max_length=20)
    property_address = models.CharField(max_length=255)
    property_image = models.URLField(blank=True, default='')

    renter_name = models.CharField(max_length=255)
    renter_phone = models.CharField(max_length=20)
    renter_email = models.EmailField(blank=True, default='')

    owner_name = models.CharField(max_length=255)
    owner_phone = models.CharField(max_length=20)

    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        db_index=True,
    )
    booking_mode = models.CharField(
        max_length=20,
        choices=BookingMode.choices,
        default=BookingMode.REQUEST,
    )

    move_in_date = models.DateField(null=True, blank=True)
    move_out_date = models.DateField(null=True, blank=True)
    duration = models.PositiveSmallIntegerField(default=1)

    rent = models.DecimalField(max_digits=12, decimal_places=2)
    deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    message = models.TextField(blank=True, default='')
    special_requests = models.TextField(blank=True, default='')

    flat = models.ForeignKey(
        'portfolio.Flat',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text='Assigned unit when an apartment booking is approved.',
    )

    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    rejection_reason = models.TextField(blank=True, default='')
    cancellation_reason = models.TextField(blank=True, default='')

    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'bookings_property_booking'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['renter', 'status']),
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        return f'{self.property_name} — {self.renter_phone} ({self.status})'
