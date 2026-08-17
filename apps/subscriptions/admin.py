from django.contrib import admin

from subscriptions.models import FeaturedBoost, OwnerSubscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'price', 'max_flats', 'highlighted', 'is_active')
    list_filter = ('tier', 'is_active', 'highlighted')


@admin.register(OwnerSubscription)
class OwnerSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'owner',
        'plan',
        'billing_cycle_start',
        'billing_cycle_end',
        'active_featured_listings',
    )
    search_fields = ('owner__phone', 'owner__name')
    list_filter = ('plan__tier',)


@admin.register(FeaturedBoost)
class FeaturedBoostAdmin(admin.ModelAdmin):
    list_display = (
        'owner',
        'property',
        'boost_option_id',
        'duration_days',
        'featured_until',
        'paid_at',
    )
    search_fields = ('owner__phone', 'property__name')
