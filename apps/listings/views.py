from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from listings.filters import PropertyFilter
from listings.models import ListingStatus, Property, PropertyReview
from listings.serializers import (
    BatchIdsSerializer,
    OwnerResponseSerializer,
    PropertySerializer,
    PropertyWriteSerializer,
    PropertyReviewSerializer,
    ReviewCreateSerializer,
)


def _published_qs():
    return (
        Property.objects.filter(
            published=True,
            listing_status=ListingStatus.PUBLISHED,
        )
        .select_related('owner')
        .prefetch_related('image_files')
    )


def _serialize_many(qs, request):
    return PropertySerializer(qs, many=True, context={'request': request}).data


def _serialize_one(obj, request):
    return PropertySerializer(obj, context={'request': request}).data


class PropertyListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = _published_qs()
        filtered = PropertyFilter(request.query_params, queryset=qs).qs

        # nearby facilities: any match (OR)
        nearby = request.query_params.getlist('nearbyFacilities') or []
        single = request.query_params.get('nearbyFacilities')
        if single and not nearby:
            nearby = [x.strip() for x in single.split(',') if x.strip()]
        if nearby:
            q = Q()
            for fac in nearby:
                q |= Q(nearby_facilities__icontains=fac)
            filtered = filtered.filter(q).distinct()

        return Response(api_success(_serialize_many(filtered, request)))

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can create listings.')
        serializer = PropertyWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        images = serializer.validated_data.get('images') or request.data.get('images')
        if not images:
            raise InvalidError('Add at least one photo')
        prop = serializer.save(
            owner=request.user,
            verification_status='pending',
            verified=False,
        )
        return Response(
            api_success(_serialize_one(prop, request)),
            status=status.HTTP_201_CREATED,
        )


class PropertyDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_object(self, pk, *, for_owner=False):
        try:
            prop = (
                Property.objects.select_related('owner')
                .prefetch_related('image_files')
                .get(pk=pk)
            )
        except Property.DoesNotExist as exc:
            raise NotFoundError('Listing not found.') from exc
        if for_owner:
            return prop
        if prop.published and prop.listing_status == ListingStatus.PUBLISHED:
            return prop
        user = self.request.user
        if user.is_authenticated and (
            prop.owner_id == user.id or user.role == 'admin'
        ):
            return prop
        raise NotFoundError('Listing not found.')

    def get(self, request, pk):
        prop = self.get_object(pk)
        return Response(api_success(_serialize_one(prop, request)))

    def patch(self, request, pk):
        prop = self.get_object(pk, for_owner=True)
        if prop.owner_id != request.user.id and request.user.role != 'admin':
            raise ForbiddenError('You can only edit your own listings.')
        serializer = PropertyWriteSerializer(
            prop,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        prop = serializer.save()
        return Response(api_success(_serialize_one(prop, request)))


class FeaturedPropertiesView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        limit = int(request.query_params.get('limit', 9))
        limit = max(1, min(limit, 50))
        now = timezone.now()
        qs = _published_qs().filter(
            Q(featured=True) & (Q(featured_until__isnull=True) | Q(featured_until__gte=now))
            | Q(verified=True),
        )
        # Score-ish ordering: featured first, then rating
        props = list(qs.order_by('-featured', '-rating', '-created_at')[:limit])
        return Response(api_success(_serialize_many(props, request)))


class PropertyMetaView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        qs = _published_qs()
        cities = sorted({c for c in qs.values_list('city', flat=True) if c})
        areas_by_city: dict[str, list[str]] = {}
        for city, area in qs.values_list('city', 'area').distinct():
            areas_by_city.setdefault(city, [])
            if area and area not in areas_by_city[city]:
                areas_by_city[city].append(area)
        for city in areas_by_city:
            areas_by_city[city].sort()
        return Response(
            api_success({'cities': cities, 'areasByCity': areas_by_city}),
        )


class PropertyRecommendationsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        try:
            current = Property.objects.get(pk=pk)
        except Property.DoesNotExist as exc:
            raise NotFoundError('Listing not found.') from exc

        limit = int(request.query_params.get('limit', 4))
        limit = max(1, min(limit, 20))
        candidates = list(
            _published_qs()
            .exclude(pk=pk)
            .filter(available=True)[:80],
        )

        def score(p: Property) -> float:
            s = 0.0
            if p.city == current.city:
                s += 3
            if p.area == current.area:
                s += 2
            if p.type == current.type:
                s += 2
            if p.gender and p.gender == current.gender:
                s += 1
            rent_diff = abs(float(p.rent) - float(current.rent)) / max(
                float(current.rent),
                1,
            )
            s += max(0, 2 - rent_diff * 4)
            if p.verified:
                s += 0.5
            s += (p.rating or 0) / 5
            return s

        ranked = sorted(candidates, key=score, reverse=True)[:limit]
        return Response(api_success(_serialize_many(ranked, request)))


class OwnerListingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            Property.objects.filter(owner=request.user)
            .select_related('owner')
            .prefetch_related('image_files')
            .order_by('-updated_at')
        )
        return Response(api_success(_serialize_many(qs, request)))


class PropertyBatchView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BatchIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data['ids']
        if not ids:
            return Response(api_success([]))
        props = {
            str(p.id): p
            for p in Property.objects.filter(id__in=ids)
            .select_related('owner')
            .prefetch_related('image_files')
        }
        ordered = [props[str(i)] for i in ids if str(i) in props]
        # Also allow public + own drafts for authenticated
        visible = []
        user = request.user
        for p in ordered:
            if p.published and p.listing_status == ListingStatus.PUBLISHED:
                visible.append(p)
            elif user.is_authenticated and (
                p.owner_id == user.id or user.role == 'admin'
            ):
                visible.append(p)
        return Response(api_success(_serialize_many(visible, request)))


class PropertyReviewListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_property(self, pk):
        try:
            return Property.objects.get(pk=pk)
        except Property.DoesNotExist as exc:
            raise NotFoundError('Listing not found.') from exc

    def get(self, request, pk):
        prop = self.get_property(pk)
        reviews = (
            PropertyReview.objects.filter(property=prop)
            .select_related('user')
            .order_by('-created_at')
        )
        data = PropertyReviewSerializer(
            reviews,
            many=True,
            context={'request': request},
        ).data
        return Response(api_success(data))

    def post(self, request, pk):
        prop = self.get_property(pk)
        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if PropertyReview.objects.filter(property=prop, user=request.user).exists():
            raise InvalidError('You already reviewed this property.')

        months = data.get('stayDurationMonths')
        review = PropertyReview.objects.create(
            property=prop,
            user=request.user,
            rating=data['rating'],
            comment=data['comment'].strip(),
            stay_duration_months=months,
            verified_stay=bool(months and months >= 1),
        )
        prop.refresh_rating_cache()
        return Response(
            api_success(
                PropertyReviewSerializer(review, context={'request': request}).data,
            ),
            status=status.HTTP_201_CREATED,
        )


class PropertyReviewSummaryView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        try:
            prop = Property.objects.get(pk=pk)
        except Property.DoesNotExist as exc:
            raise NotFoundError('Listing not found.') from exc

        reviews = PropertyReview.objects.filter(property=prop)
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        total = 0
        rating_sum = 0
        for r in reviews.only('rating'):
            distribution[r.rating] = distribution.get(r.rating, 0) + 1
            total += 1
            rating_sum += r.rating

        avg = round(rating_sum / total, 2) if total else 0
        return Response(
            api_success(
                {
                    'averageRating': avg,
                    'totalReviews': total,
                    'distribution': distribution,
                },
            ),
        )


class PropertyReviewRespondView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, review_id):
        try:
            prop = Property.objects.get(pk=pk)
        except Property.DoesNotExist as exc:
            raise NotFoundError('Listing not found.') from exc

        if prop.owner_id != request.user.id and request.user.role != 'admin':
            raise ForbiddenError('Only the listing owner can respond.')

        try:
            review = PropertyReview.objects.select_related('user').get(
                pk=review_id,
                property=prop,
            )
        except PropertyReview.DoesNotExist as exc:
            raise NotFoundError('Review not found.') from exc

        serializer = OwnerResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review.owner_response = serializer.validated_data['response'].strip()
        review.owner_response_date = timezone.now()
        review.save(update_fields=['owner_response', 'owner_response_date', 'updated_at'])
        return Response(
            api_success(
                PropertyReviewSerializer(review, context={'request': request}).data,
            ),
        )
