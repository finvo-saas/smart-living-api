from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import InvalidError, NotFoundError
from discovery.services.area_pages import (
    get_area_page,
    list_area_pages,
    listings_for_area,
)
from discovery.services.geocode import geocode_address
from listings.serializers import PropertySerializer


class AreaSeoListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(api_success(list_area_pages()))


class AreaSeoDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, city_slug, area_slug):
        category = request.query_params.get('category') or 'mess'
        try:
            limit = int(request.query_params.get('limit', 24))
        except (TypeError, ValueError):
            limit = 24
        meta, props = listings_for_area(
            city_slug,
            area_slug,
            category=category,
            limit=limit,
        )
        if meta is None:
            raise NotFoundError('Area page not found.')
        return Response(
            api_success(
                {
                    'area': {
                        'citySlug': meta['citySlug'],
                        'city': meta['city'],
                        'areaSlug': meta['areaSlug'],
                        'area': meta['area'],
                        'path': f"/{meta['citySlug']}/{meta['areaSlug']}/{category}",
                    },
                    'category': category,
                    'listings': PropertySerializer(
                        props,
                        many=True,
                        context={'request': request},
                    ).data,
                },
            ),
        )


class SitemapDataView(APIView):
    """Public inventory the frontend turns into sitemap.xml entries."""

    permission_classes = [AllowAny]
    authentication_classes = []

    # Sitemaps cap at 50k URLs; stay well inside that per entity type.
    MAX_PER_TYPE = 5000

    @staticmethod
    def _rows(qs, fields):
        return [
            {
                'id': str(row['id']),
                'name': row.get('name') or '',
                'city': row.get('city') or '',
                'area': row.get('area') or '',
                'updatedAt': row['updated_at'].isoformat() if row.get('updated_at') else None,
            }
            for row in qs.values(*fields)
        ]

    def get(self, request):
        from hotels.models import Hotel
        from listings.models import ListingStatus, Property
        from mess.models import Mess

        limit = self.MAX_PER_TYPE

        listings = Property.objects.filter(
            published=True,
            listing_status=ListingStatus.PUBLISHED,
            flagged_unavailable_at__isnull=True,
        ).order_by('-updated_at')[:limit]
        hotels = Hotel.objects.filter(is_deleted=False).order_by('-updated_at')[:limit]
        messes = Mess.objects.filter(
            is_deleted=False,
            flagged_unavailable_at__isnull=True,
        ).order_by('-updated_at')[:limit]

        return Response(
            api_success(
                {
                    'listings': self._rows(
                        listings,
                        ('id', 'name', 'city', 'area', 'updated_at'),
                    ),
                    'hotels': self._rows(
                        hotels,
                        ('id', 'name', 'city', 'area', 'updated_at'),
                    ),
                    'messes': self._rows(
                        messes,
                        ('id', 'name', 'city', 'updated_at'),
                    ),
                },
            ),
        )


class GeocodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        address = (request.query_params.get('address') or '').strip()
        city = (request.query_params.get('city') or '').strip()
        area = (request.query_params.get('area') or '').strip()
        if len(address) < 3 and not (city and area):
            raise InvalidError('address (or city+area) is required.')
        hit = geocode_address(address or f'{area}, {city}', city=city, area=area)
        if not hit:
            raise NotFoundError('Could not geocode that address.')
        return Response(api_success(hit))
