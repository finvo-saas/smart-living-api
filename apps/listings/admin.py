from django.contrib import admin

from core.admin import TimestampedModelAdmin
from listings.models import Property, PropertyImage, PropertyReview


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Property)
class PropertyAdmin(TimestampedModelAdmin):
    list_display = (
        'name',
        'type',
        'city',
        'area',
        'rent',
        'published',
        'listing_status',
        'featured',
        'open_seats',
        'owner',
    )
    list_filter = ('type', 'city', 'published', 'listing_status', 'featured', 'verified')
    search_fields = ('name', 'area', 'address', 'owner__phone')
    inlines = [PropertyImageInline]


@admin.register(PropertyReview)
class PropertyReviewAdmin(TimestampedModelAdmin):
    list_display = (
        'property',
        'user',
        'rating',
        'cleanliness',
        'security',
    )
    list_filter = ('rating',)
    search_fields = ('property__name', 'user__phone', 'comment')
