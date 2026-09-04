from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import InvalidError
from discovery.services.area_compare import compare_areas, list_areas
from discovery.services.pois import nearby_pois


class NearbyPOIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lng = float(request.query_params.get('lng'))
        except (TypeError, ValueError) as exc:
            raise InvalidError('lat and lng are required.') from exc
        try:
            radius = int(request.query_params.get('radius', 1500))
        except (TypeError, ValueError):
            radius = 1500
        return Response(api_success(nearby_pois(lat, lng, radius)))


class AreaListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        city = request.query_params.get('city') or None
        try:
            limit = int(request.query_params.get('limit', 40))
        except (TypeError, ValueError):
            limit = 40
        return Response(api_success(list_areas(city=city, limit=max(1, min(limit, 80)))))


class AreaCompareView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        raw = request.query_params.get('areas') or ''
        names = [part.strip() for part in raw.split(',') if part.strip()]
        city = request.query_params.get('city') or None
        return Response(api_success(compare_areas(names, city=city)))
