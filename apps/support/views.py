from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from core.envelope import api_success
from core.exceptions import ForbiddenError, NotFoundError
from hotels.models import HotelBooking
from mess.models import MessStudent
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
    """Every platform user an owner is responsible for, across all verticals."""
    tenant_ids = set(
        Tenancy.objects.filter(
            flat__building__owner=owner,
            status=TenancyStatus.ACTIVE,
        ).values_list('tenant_id', flat=True),
    )
    tenant_ids.update(
        MessStudent.objects.filter(
            mess__owner=owner,
            is_active=True,
            is_deleted=False,
            user__isnull=False,
        ).values_list('user_id', flat=True),
    )
    tenant_ids.update(
        HotelBooking.objects.filter(
            hotel__owner=owner,
            is_deleted=False,
        ).values_list('user_id', flat=True),
    )
    tenant_ids.discard(None)
    return tenant_ids


def _owner_complaints_qs(owner):
    """An owner sees their own complaints plus those raised by their renters."""
    return _complaint_qs().filter(
        Q(user_id__in=_tenant_user_ids_for_owner(owner)) | Q(user=owner),
    )


class ComplaintListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        owner_view = request.query_params.get('ownerView') in ('1', 'true', 'True')

        if user.role == Role.ADMIN:
            qs = _complaint_qs() if owner_view else _complaint_qs().filter(user=user)
        elif user.role == Role.OWNER:
            # ownerView never widens scope beyond the owner's own renters.
            qs = _owner_complaints_qs(user)
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
        is_creator = complaint.user_id == user.id
        is_managing_owner = (
            user.role == Role.OWNER
            and complaint.user_id in _tenant_user_ids_for_owner(user)
        )
        is_staff = user.role == Role.ADMIN or is_managing_owner

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
