from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from core.envelope import api_success
from core.exceptions import ForbiddenError, NotFoundError
from portfolio.models import Tenancy, TenancyStatus
from support.models import Complaint, ComplaintStatus
from support.serializers import (
    ComplaintCreateSerializer,
    ComplaintSerializer,
    ComplaintStatusUpdateSerializer,
)


def _complaint_qs():
    return Complaint.objects.filter(is_deleted=False).select_related('user')


def _get_complaint(pk):
    try:
        return _complaint_qs().get(pk=pk)
    except Complaint.DoesNotExist as exc:
        raise NotFoundError('Complaint not found.') from exc


def _tenant_user_ids_for_owner(owner):
    return Tenancy.objects.filter(
        flat__building__owner=owner,
        status=TenancyStatus.ACTIVE,
    ).values_list('tenant_id', flat=True)


class ComplaintListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        owner_view = request.query_params.get('ownerView') in ('1', 'true', 'True')

        if owner_view and user.role in (Role.OWNER, Role.ADMIN):
            qs = _complaint_qs()
        elif user.role == Role.OWNER:
            tenant_ids = _tenant_user_ids_for_owner(user)
            qs = _complaint_qs().filter(user_id__in=tenant_ids)
        else:
            qs = _complaint_qs().filter(user=user)

        data = ComplaintSerializer(qs.order_by('-created_at'), many=True).data
        return Response(api_success(data))

    def post(self, request):
        ser = ComplaintCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        complaint = ser.create_complaint(request.user)
        return Response(
            api_success(ComplaintSerializer(complaint).data),
            status=status.HTTP_201_CREATED,
        )


class ComplaintStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        complaint = _get_complaint(pk)
        user = request.user
        is_staff = user.role in (Role.OWNER, Role.ADMIN)
        is_creator = complaint.user_id == user.id

        if not is_staff and not is_creator:
            raise ForbiddenError('You cannot update this complaint.')

        ser = ComplaintStatusUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_status = ser.validated_data['status']

        if not is_staff and new_status != ComplaintStatus.OPEN:
            raise ForbiddenError('Only owners or admins can change complaint status.')

        complaint.status = new_status
        if 'response' in ser.validated_data:
            complaint.response = ser.validated_data['response']
        if new_status == ComplaintStatus.RESOLVED:
            complaint.resolved_at = timezone.now()
        elif new_status != ComplaintStatus.RESOLVED:
            complaint.resolved_at = None
        complaint.save()

        return Response(api_success(ComplaintSerializer(complaint).data))
