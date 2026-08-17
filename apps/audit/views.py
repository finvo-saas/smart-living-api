from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from audit.serializers import AuditLogCreateSerializer, AuditLogSerializer
from audit.services import create_audit_log
from core.envelope import api_success


class AuditLogCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AuditLogCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = create_audit_log(request.user, request=request, **serializer.validated_data)
        return Response(
            api_success(AuditLogSerializer(log).data),
            status=status.HTTP_201_CREATED,
        )


def filter_audit_logs(*, entity=None, action=None, entity_type=None, user_id=None):
    qs = AuditLog.objects.all().order_by('-created_at')
    if entity:
        qs = qs.filter(entity_id=str(entity))
    if action:
        qs = qs.filter(action=action)
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    if user_id:
        qs = qs.filter(user_id=user_id)
    return qs


def serialize_audit_logs(qs):
    return AuditLogSerializer(qs, many=True).data
