from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import InvalidError
from core.services.media import media_storage


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            api_success(
                {
                    'status': 'ok',
                    'service': 'smart-living-api',
                    'version': '1.0.0',
                },
            ),
        )


class MediaUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded = request.FILES.get('file')
        if not uploaded:
            raise InvalidError('Choose a file to upload.')
        kind = (request.data.get('kind') or 'image').strip().lower()
        stored = media_storage.upload(uploaded, kind, request=request)
        return Response(
            api_success(
                {
                    'url': stored.url,
                    'key': stored.key,
                    'name': uploaded.name,
                    'kind': stored.kind,
                },
            ),
        )
