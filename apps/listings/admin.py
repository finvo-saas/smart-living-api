from django.contrib import admin

from core.admin import TimestampedModelAdmin
from listings.models import Property, PropertyImage, PropertyReview, ListingTakenReport


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


@admin.register(ListingTakenReport)
class ListingTakenReportAdmin(TimestampedModelAdmin):
    list_display = ('listing', 'reporter', 'status', 'created_at', 'resolved_at')
    list_filter = ('status',)
    search_fields = ('listing__name',)


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
