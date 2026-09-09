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
    SubscriptionPlanSerializer,
    UpgradePlanSerializer,
)
from subscriptions.services import (
    FEATURED_BOOST_OPTIONS,
    ensure_default_plans,
    get_boost_option,
    get_flat_limit_status,
    get_or_create_owner_subscription,
    get_owner_usage_status,
    upgrade_owner_plan,
)


class OwnerSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = get_or_create_owner_subscription(request.user)
        return Response(api_success(OwnerSubscriptionSerializer(sub).data))


class SubscriptionPlansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ensure_default_plans()
        from subscriptions.models import SubscriptionPlan

        qs = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
        return Response(api_success(SubscriptionPlanSerializer(qs, many=True).data))


class FlatLimitStatusView(APIView):
    """Legacy apartment-only limit. Prefer OwnerUsageStatusView."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(api_success(get_flat_limit_status(request.user)))


class OwnerUsageStatusView(APIView):
    """Per-module usage (mess / flats / hotels) for the logged-in owner."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(api_success(get_owner_usage_status(request.user)))


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
        listing_id = serializer.validated_data.get('listingId')
        hotel_id = serializer.validated_data.get('hotelId')
        mess_id = serializer.validated_data.get('messId')
        target_type = serializer.validated_data.get('targetType') or 'listing'
        boost_id = serializer.validated_data['boostId']

        boost = get_boost_option(boost_id)
        if not boost:
            raise InvalidError('Invalid boost option.')

        until = timezone.localdate() + timedelta(days=boost['durationDays'])
        until_dt = timezone.make_aware(datetime.combine(until, datetime.max.time()))
        prop = hotel = mess = None

        if target_type == 'hotel' or hotel_id:
            from hotels.models import Hotel

            try:
                hotel = Hotel.objects.get(pk=hotel_id)
            except Hotel.DoesNotExist as exc:
                raise NotFoundError('Hotel not found.') from exc
            if hotel.owner_id != request.user.id and request.user.role != 'admin':
                raise ForbiddenError('You can only boost your own hotels.')
            hotel.featured = True
            hotel.featured_until = until_dt
            hotel.save(update_fields=['featured', 'featured_until', 'updated_at'])
            target_type = 'hotel'
        elif target_type == 'mess' or mess_id:
            from mess.models import Mess

            try:
                mess = Mess.objects.get(pk=mess_id)
            except Mess.DoesNotExist as exc:
                raise NotFoundError('Mess not found.') from exc
            if mess.owner_id != request.user.id and request.user.role != 'admin':
                raise ForbiddenError('You can only boost your own mess.')
            mess.featured = True
            mess.featured_until = until_dt
            mess.save(update_fields=['featured', 'featured_until', 'updated_at'])
            target_type = 'mess'
        else:
            if not listing_id:
                raise InvalidError('listingId is required.')
            try:
                prop = Property.objects.get(pk=listing_id)
            except Property.DoesNotExist as exc:
                raise NotFoundError('Listing not found.') from exc
            if prop.owner_id != request.user.id and request.user.role != 'admin':
                raise ForbiddenError('You can only boost your own listings.')
            if not prop.published or not prop.available:
                raise InvalidError('Only published available listings can be boosted.')
            prop.featured = True
            prop.featured_until = until_dt
            prop.save(update_fields=['featured', 'featured_until', 'updated_at'])
            target_type = 'listing'

        FeaturedBoost.objects.create(
            owner=request.user,
            property=prop,
            hotel=hotel,
            mess=mess,
            target_type=target_type,
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


class AdCampaignListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from subscriptions.models import AdCampaign
        from subscriptions.services_campaigns import serialize_campaign

        qs = AdCampaign.objects.filter(owner=request.user).order_by('-created_at')[:50]
        return Response(api_success([serialize_campaign(c) for c in qs]))

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can create campaigns.')
        from django.utils.dateparse import parse_datetime
        from subscriptions.services_campaigns import create_campaign, serialize_campaign

        data = dict(request.data)
        if data.get('startsAt'):
            data['startsAt'] = parse_datetime(str(data['startsAt'])) or timezone.now()
        if data.get('endsAt'):
            data['endsAt'] = parse_datetime(str(data['endsAt']))
        campaign = create_campaign(request.user, data)
        return Response(
            api_success(serialize_campaign(campaign)),
            status=status.HTTP_201_CREATED,
        )


class AdCampaignAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from subscriptions.services_campaigns import campaign_analytics

        return Response(api_success(campaign_analytics(request.user)))


class AdCampaignDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        from subscriptions.models import AdCampaign
        from subscriptions.services_campaigns import serialize_campaign

        try:
            campaign = AdCampaign.objects.get(pk=pk, owner=request.user)
        except AdCampaign.DoesNotExist as exc:
            raise NotFoundError('Campaign not found.') from exc
        status_value = request.data.get('status')
        if status_value in dict(AdCampaign.Status.choices):
            campaign.status = status_value
            campaign.save(update_fields=['status', 'updated_at'])
        return Response(api_success(serialize_campaign(campaign)))

    def post(self, request, pk):
        """Record a click or impression event."""
        from subscriptions.models import AdCampaign
        from subscriptions.services_campaigns import serialize_campaign

        try:
            campaign = AdCampaign.objects.get(pk=pk)
        except AdCampaign.DoesNotExist as exc:
            raise NotFoundError('Campaign not found.') from exc
        event = (request.data.get('event') or 'impression').lower()
        if event == 'click':
            campaign.clicks += 1
            campaign.spend = float(campaign.spend) + float(campaign.bid_amount) * 0.01
            campaign.save(update_fields=['clicks', 'spend', 'updated_at'])
        else:
            campaign.impressions += 1
            campaign.save(update_fields=['impressions', 'updated_at'])
        return Response(api_success(serialize_campaign(campaign)))
