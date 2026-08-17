from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success


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
