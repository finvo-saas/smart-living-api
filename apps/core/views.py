from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import InvalidError
from core.services.media import media_storage
from core.services.media_library import (
    assert_owner_can_delete,
    forget_key,
    list_assets,
    record_upload,
    serialize_asset,
)


class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

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


class MediaLibraryView(APIView):
    """List the signed-in owner's uploads. Never includes other owners."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        kind = (request.query_params.get('kind') or '').strip().lower()
        images_only = (request.query_params.get('images') or '1').strip().lower() not in (
            '0',
            'false',
            'no',
        )
        try:
            limit = int(request.query_params.get('limit') or 60)
        except (TypeError, ValueError):
            limit = 60
        assets = list_assets(
            request.user,
            kind=kind,
            images_only=images_only,
            limit=limit,
        )
        return Response(
            api_success([serialize_asset(asset, request) for asset in assets]),
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
        asset = record_upload(
            request.user,
            key=stored.key,
            url=stored.url,
            kind=stored.kind,
            original_name=uploaded.name or '',
            content_type=(uploaded.content_type or '').split(';')[0].strip(),
            size_bytes=getattr(uploaded, 'size', 0) or 0,
        )
        payload = serialize_asset(asset, request)
        payload['name'] = payload.get('name') or uploaded.name
        return Response(api_success(payload))


class MediaDeleteView(APIView):
    """Remove an object from Spaces and the owner's media index."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        url = (request.data.get('url') or '').strip()
        key = (request.data.get('key') or '').strip()
        kind = (request.data.get('kind') or '').strip().lower() or None
        if not url and not key:
            raise InvalidError('Provide a media url or key to delete.')
        resolved = (key or '').strip() or media_storage.key_from_url(url)
        if kind:
            resolved = media_storage.assert_deletable_key(resolved, kind=kind)
        else:
            resolved = media_storage.assert_deletable_key(resolved)
        owned = assert_owner_can_delete(request.user, resolved)
        private = bool(owned and owned.visibility == 'private')
        if kind:
            private = private or media_storage.spec(kind).private
        media_storage.delete(resolved, private=private)
        forget_key(resolved)
        return Response(api_success({'deleted': True, 'key': resolved}))
