from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import NotFoundError
from discovery.services.universities import (
    get_university,
    list_universities,
    listings_near_university,
)
from listings.serializers import PropertySerializer


class UniversityListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(api_success(list_universities()))


class UniversityDetailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        category = request.query_params.get('category') or 'mess'
        try:
            limit = int(request.query_params.get('limit', 24))
        except (TypeError, ValueError):
            limit = 24
        uni, props = listings_near_university(slug, category=category, limit=limit)
        if uni is None:
            raise NotFoundError('University not found.')
        return Response(
            api_success(
                {
                    'university': uni,
                    'category': category,
                    'listings': PropertySerializer(
                        props,
                        many=True,
                        context={'request': request},
                    ).data,
                },
            ),
        )
