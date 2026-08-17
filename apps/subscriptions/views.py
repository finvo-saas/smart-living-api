from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from listings.models import Property
from subscriptions.models import FeaturedBoost
from subscriptions.serializers import (
    FeaturedBoostSerializer,
    OwnerSubscriptionSerializer,
    UpgradePlanSerializer,
)
from subscriptions.services import (
    FEATURED_BOOST_OPTIONS,
    get_boost_option,
    get_flat_limit_status,
    get_or_create_owner_subscription,
    upgrade_owner_plan,
)


class OwnerSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = get_or_create_owner_subscription(request.user)
        return Response(api_success(OwnerSubscriptionSerializer(sub).data))


class FlatLimitStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(api_success(get_flat_limit_status(request.user)))


class UpgradeSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can upgrade subscriptions.')
        serializer = UpgradePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sub = upgrade_owner_plan(request.user, serializer.validated_data['tier'])
        return Response(api_success(OwnerSubscriptionSerializer(sub).data))


class FeaturedBoostView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can purchase featured boosts.')

        serializer = FeaturedBoostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing_id = serializer.validated_data['listingId']
        boost_id = serializer.validated_data['boostId']

        boost = get_boost_option(boost_id)
        if not boost:
            raise InvalidError('Invalid boost option.')

        try:
            prop = Property.objects.get(pk=listing_id)
        except Property.DoesNotExist as exc:
            raise NotFoundError('Listing not found.') from exc

        if prop.owner_id != request.user.id and request.user.role != 'admin':
            raise ForbiddenError('You can only boost your own listings.')

        until = timezone.localdate() + timedelta(days=boost['durationDays'])
        prop.featured = True
        prop.featured_until = timezone.make_aware(
            datetime.combine(until, datetime.max.time()),
        )
        prop.save(update_fields=['featured', 'featured_until', 'updated_at'])

        FeaturedBoost.objects.create(
            owner=request.user,
            property=prop,
            boost_option_id=boost_id,
            duration_days=boost['durationDays'],
            price=boost['price'],
            featured_until=until,
        )

        sub = get_or_create_owner_subscription(request.user)
        sub.active_featured_listings += 1
        sub.save(update_fields=['active_featured_listings', 'updated_at'])

        return Response(
            api_success({'featuredUntil': until.isoformat()}),
            status=status.HTTP_201_CREATED,
        )


class FeaturedBoostOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(api_success(FEATURED_BOOST_OPTIONS))
