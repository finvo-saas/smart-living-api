from django.contrib import admin

from listings.models import Property, PropertyImage, PropertyReview


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'type',
        'city',
        'area',
        'rent',
        'published',
        'listing_status',
        'featured',
        'owner',
    )
    list_filter = ('type', 'city', 'published', 'listing_status', 'featured', 'verified')
    search_fields = ('name', 'area', 'address', 'owner__phone')
    inlines = [PropertyImageInline]


@admin.register(PropertyReview)
class PropertyReviewAdmin(admin.ModelAdmin):
    list_display = ('property', 'user', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('property__name', 'user__phone', 'comment')
