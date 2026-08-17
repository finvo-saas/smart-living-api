from django.contrib import admin

from hotels.models import Hotel, HotelBooking, HotelReview, Room, RoomPrice


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'type',
        'city',
        'area',
        'verified',
        'featured',
        'total_rooms',
        'available_rooms',
        'owner',
        'is_deleted',
    )
    list_filter = ('type', 'city', 'verified', 'featured', 'is_deleted')
    search_fields = ('name', 'area', 'address', 'owner__phone')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'room_number', 'type', 'floor', 'base_price', 'available')
    list_filter = ('type', 'available')
    search_fields = ('room_number', 'hotel__name')


@admin.register(RoomPrice)
class RoomPriceAdmin(admin.ModelAdmin):
    list_display = ('room', 'date', 'price', 'is_weekend', 'is_special_offer')
    list_filter = ('is_weekend', 'is_special_offer')
    date_hierarchy = 'date'


@admin.register(HotelBooking)
class HotelBookingAdmin(admin.ModelAdmin):
    list_display = (
        'hotel',
        'room',
        'guest_name',
        'check_in',
        'check_out',
        'status',
        'payment_status',
        'total_amount',
        'is_deleted',
    )
    list_filter = ('status', 'payment_status', 'is_deleted')
    search_fields = ('guest_name', 'guest_phone', 'hotel__name')


@admin.register(HotelReview)
class HotelReviewAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('hotel__name', 'user__phone', 'comment')
