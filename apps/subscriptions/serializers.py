from rest_framework import serializers

from subscriptions.models import OwnerSubscription, SubscriptionPlan


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    tier = serializers.CharField(read_only=True)
    maxFlats = serializers.IntegerField(source='max_flats', read_only=True)
    price = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = ('tier', 'name', 'price', 'maxFlats', 'features', 'highlighted')

    def get_price(self, obj):
        return float(obj.price)


class OwnerSubscriptionSerializer(serializers.ModelSerializer):
    ownerId = serializers.UUIDField(source='owner_id', read_only=True)
    planTier = serializers.CharField(source='plan.tier', read_only=True)
    billingCycleStart = serializers.DateField(source='billing_cycle_start', read_only=True)
    billingCycleEnd = serializers.DateField(source='billing_cycle_end', read_only=True)
    flatsUsed = serializers.IntegerField(source='flats_used', read_only=True)
    activeFeaturedListings = serializers.IntegerField(
        source='active_featured_listings',
        read_only=True,
    )

    class Meta:
        model = OwnerSubscription
        fields = (
            'ownerId',
            'planTier',
            'billingCycleStart',
            'billingCycleEnd',
            'flatsUsed',
            'activeFeaturedListings',
        )


class UpgradePlanSerializer(serializers.Serializer):
    tier = serializers.ChoiceField(choices=['basic', 'premium'])


class FeaturedBoostSerializer(serializers.Serializer):
    listingId = serializers.UUIDField(required=False)
    hotelId = serializers.UUIDField(required=False)
    messId = serializers.UUIDField(required=False)
    targetType = serializers.ChoiceField(
        choices=['listing', 'hotel', 'mess'],
        required=False,
        default='listing',
    )
    boostId = serializers.CharField()
