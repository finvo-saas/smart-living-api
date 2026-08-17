from django.contrib import admin

from bookings.models import PropertyBooking


@admin.register(PropertyBooking)
class PropertyBookingAdmin(admin.ModelAdmin):
    list_display = (
        'property_name',
        'renter_phone',
        'owner_phone',
        'status',
        'booking_mode',
        'move_in_date',
        'total_amount',
        'is_deleted',
        'created_at',
    )
    list_filter = ('status', 'booking_mode', 'property_type', 'is_deleted')
    search_fields = (
        'property_name',
        'renter_phone',
        'owner_phone',
        'renter_name',
        'owner_name',
    )
    readonly_fields = ('created_at', 'updated_at')
