from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from discovery.models import Favorite, SavedSearch, SearchHistory
from discovery.serializers import (
    FavoriteSerializer,
    SavedSearchSerializer,
    SavedSearchWriteSerializer,
    SearchHistorySerializer,
    SearchHistoryWriteSerializer,
    ToggleFavoriteSerializer,
)
from discovery.services.feed import build_feed, unified_search
from discovery.services.freshness import confirm_object, flag_unavailable
from hotels.models import Hotel
from listings.models import ListingStatus, Property
from listings.serializers import PropertySerializer
from mess.models import Mess


class FavoriteListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favs = (
            Favorite.objects.filter(user=request.user)
            .select_related('property', 'property__owner')
            .prefetch_related('property__image_files')
        )
        return Response(
            api_success(
                FavoriteSerializer(
                    favs,
                    many=True,
                    context={'request': request},
                ).data,
            ),
        )


class FavoriteToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ToggleFavoriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_id = serializer.validated_data['propertyId']

        try:
            prop = Property.objects.get(pk=property_id)
        except Property.DoesNotExist as exc:
            raise NotFoundError('Listing not found.') from exc

        existing = Favorite.objects.filter(user=request.user, property=prop).first()
        if existing:
            existing.delete()
            return Response(api_success({'added': False}))

        Favorite.objects.create(user=request.user, property=prop)
        return Response(api_success({'added': True}), status=status.HTTP_201_CREATED)


class FavoriteCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        property_id = request.query_params.get(
            'property_id',
        ) or request.query_params.get('propertyId')
        if not property_id:
            return Response(api_success(False))
        exists = Favorite.objects.filter(
            user=request.user,
            property_id=property_id,
        ).exists()
        return Response(api_success(exists))


class SavedSearchListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = SavedSearch.objects.filter(user=request.user)
        return Response(api_success(SavedSearchSerializer(qs, many=True).data))

    def post(self, request):
        serializer = SavedSearchWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(user=request.user)
        return Response(
            api_success(SavedSearchSerializer(obj).data),
            status=status.HTTP_201_CREATED,
        )


class SavedSearchDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return SavedSearch.objects.get(pk=pk, user=user)
        except SavedSearch.DoesNotExist as exc:
            raise NotFoundError('Saved search not found.') from exc

    def patch(self, request, pk):
        obj = self.get_object(pk, request.user)
        serializer = SavedSearchWriteSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(api_success(SavedSearchSerializer(obj).data))

    def delete(self, request, pk):
        obj = self.get_object(pk, request.user)
        obj.delete()
        return Response(api_success(None))


class SearchHistoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = SearchHistory.objects.filter(user=request.user)[:50]
        return Response(api_success(SearchHistorySerializer(qs, many=True).data))

    def post(self, request):
        serializer = SearchHistoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        obj = SearchHistory.objects.create(
            user=request.user,
            search_query=data.get('searchQuery', ''),
            filters=data.get('filters') or {},
            result_count=data.get('resultCount') or 0,
        )
        return Response(
            api_success(SearchHistorySerializer(obj).data),
            status=status.HTTP_201_CREATED,
        )


class SearchHistoryClearView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        SearchHistory.objects.filter(user=request.user).delete()
        return Response(api_success(None))


class SearchHistoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        deleted, _ = SearchHistory.objects.filter(pk=pk, user=request.user).delete()
        if not deleted:
            raise NotFoundError('History entry not found.')
        return Response(api_success(None))


def _filters_match(prop: Property, filters: dict) -> bool:
    ptype = filters.get('propertyType') or filters.get('type')
    if ptype and ptype != 'all' and prop.type != ptype:
        return False
    if filters.get('city') and prop.city.lower() != str(filters['city']).lower():
        return False
    if filters.get('area') and prop.area.lower() != str(filters['area']).lower():
        return False
    rent_range = filters.get('rentRange')
    if isinstance(rent_range, (list, tuple)) and len(rent_range) == 2:
        lo, hi = float(rent_range[0]), float(rent_range[1])
        rent = float(prop.rent)
        if rent < lo or rent > hi:
            return False
    gender = filters.get('gender')
    if gender and prop.gender and prop.gender not in (gender, 'mixed'):
        return False
    if filters.get('verifiedOnly') and not prop.verified:
        return False
    if filters.get('instantBook') and not prop.instant_book:
        return False
    return True


class SearchNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        week_ago = timezone.now() - timedelta(days=7)
        active = SavedSearch.objects.filter(user=request.user, is_active=True)
        published = list(
            Property.objects.filter(
                published=True,
                listing_status=ListingStatus.PUBLISHED,
                created_at__gte=week_ago,
            )
            .select_related('owner')
            .prefetch_related('image_files'),
        )

        notifications = []
        for saved in active:
            matches = [p for p in published if _filters_match(p, saved.filters or {})]
            if not matches:
                continue
            notifications.append(
                {
                    'savedSearch': SavedSearchSerializer(saved).data,
                    'newMatches': PropertySerializer(
                        matches,
                        many=True,
                        context={'request': request},
                    ).data,
                    'matchCount': len(matches),
                },
            )
        return Response(api_success(notifications))


def _load_target(target_type: str, target_id):
    mapping = {
        'listing': Property,
        'property': Property,
        'hotel': Hotel,
        'mess': Mess,
    }
    model = mapping.get((target_type or '').lower())
    if not model:
        raise InvalidError('targetType must be listing, hotel, or mess.')
    try:
        return model.objects.get(pk=target_id)
    except model.DoesNotExist as exc:
        raise NotFoundError('Item not found.') from exc


def _assert_owner(user, obj):
    owner_id = getattr(obj, 'owner_id', None)
    if owner_id != user.id and user.role != 'admin':
        raise ForbiddenError('Only the owner can confirm this listing.')


class DiscoverFeedView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        limit = int(request.query_params.get('limit', 8))
        limit = max(1, min(limit, 24))
        return Response(api_success(build_feed(request, limit=limit)))


class DiscoverSearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(api_success(unified_search(request)))


class DiscoverConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        target_type = request.data.get('targetType') or request.data.get('type')
        target_id = request.data.get('id') or request.data.get('targetId')
        if not target_id:
            raise InvalidError('id is required.')
        obj = _load_target(target_type, target_id)
        _assert_owner(request.user, obj)
        confirm_object(obj)
        return Response(api_success({'confirmed': True, 'id': str(obj.id)}))


class DiscoverReportView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        target_type = request.data.get('targetType') or request.data.get('type')
        target_id = request.data.get('id') or request.data.get('targetId')
        if not target_id:
            raise InvalidError('id is required.')
        obj = _load_target(target_type, target_id)
        flag_unavailable(obj)
        return Response(api_success({'reported': True, 'id': str(obj.id)}))


class HeartbeatPublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        from discovery.models import HeartbeatPing
        from discovery.services.heartbeat import serialize_ping_public

        ping = HeartbeatPing.objects.filter(token=token).first()
        if not ping:
            raise NotFoundError('This confirm link is invalid.')
        return Response(api_success(serialize_ping_public(ping)))

    def post(self, request, token):
        from django.core.exceptions import ObjectDoesNotExist

        from discovery.models import HeartbeatPing
        from discovery.services.heartbeat import respond_to_ping, serialize_ping_public

        ping = HeartbeatPing.objects.filter(token=token).first()
        if not ping:
            raise NotFoundError('This confirm link is invalid.')
        action = (request.data.get('action') or '').strip().lower()
        try:
            ping = respond_to_ping(ping, action)
        except ValueError as exc:
            if str(exc) == 'expired':
                raise InvalidError('This confirm link has expired.') from exc
            raise InvalidError('Use action "available" or "full".') from exc
        except ObjectDoesNotExist as exc:
            raise NotFoundError('The listing is no longer on the platform.') from exc
        return Response(api_success(serialize_ping_public(ping)))
