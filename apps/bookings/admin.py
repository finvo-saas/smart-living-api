from django.contrib import admin

from bookings.models import PropertyBooking
from core.admin import TimestampedModelAdmin


@admin.register(PropertyBooking)
class PropertyBookingAdmin(TimestampedModelAdmin):
    list_display = (
        'property_name',
        'renter_phone',
        'owner_phone',
        'status',
        'booking_mode',
        'move_in_date',
        'total_amount',
        'is_deleted',
    )
    list_filter = ('status', 'booking_mode', 'property_type', 'is_deleted')
    search_fields = (
        'property_name',
        'renter_phone',
        'owner_phone',
        'renter_name',
        'owner_name',
    )
