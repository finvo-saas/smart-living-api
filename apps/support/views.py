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
from support.models import Complaint, ComplaintMessage, ComplaintStatus
from support.serializers import (
    ComplaintCreateSerializer,
    ComplaintMessageCreateSerializer,
    ComplaintMessageSerializer,
    ComplaintSerializer,
    ComplaintStatusUpdateSerializer,
)


def _complaint_qs():
    return (
        Complaint.objects.filter(is_deleted=False)
        .select_related('user', 'building', 'flat')
        .prefetch_related('messages')
    )


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
        Q(user_id__in=_tenant_user_ids_for_owner(owner))
        | Q(user=owner)
        | Q(building__owner=owner),
    )


def _is_managing_owner(user, complaint: Complaint) -> bool:
    if user.role != Role.OWNER:
        return False
    if complaint.user_id in _tenant_user_ids_for_owner(user):
        return True
    if complaint.building_id and complaint.building.owner_id == user.id:
        return True
    if complaint.scope_type and complaint.scope_id:
        from ops.services import can_manage_scope

        return can_manage_scope(user, complaint.scope_type, complaint.scope_id)
    return False


def _can_access_complaint(user, complaint: Complaint) -> bool:
    if user.role == Role.ADMIN:
        return True
    if complaint.user_id == user.id:
        return True
    if user.role == Role.OWNER and _is_managing_owner(user, complaint):
        return True
    return False


class ComplaintListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        owner_view = request.query_params.get('ownerView') in ('1', 'true', 'True')

        if user.role == Role.ADMIN:
            qs = _complaint_qs() if owner_view else _complaint_qs().filter(user=user)
        elif user.role == Role.OWNER:
            qs = _owner_complaints_qs(user)
        else:
            qs = _complaint_qs().filter(user=user)

        data = ComplaintSerializer(qs.order_by('-created_at'), many=True).data
        return Response(api_success(data))

    def post(self, request):
        ser = ComplaintCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        complaint = ser.create_complaint(request.user)
        from support.notify import schedule_complaint_created

        schedule_complaint_created(complaint.id)
        complaint = _get_complaint(complaint.id)
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
        is_managing_owner = _is_managing_owner(user, complaint)
        is_staff = user.role == Role.ADMIN or is_managing_owner

        if not is_staff and not is_creator:
            raise ForbiddenError('You cannot update this complaint.')

        ser = ComplaintStatusUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Creator (or staff) may edit original ticket content.
        content_keys = {'title', 'description', 'category'}
        if content_keys & set(data.keys()):
            if not is_creator and not is_staff:
                raise ForbiddenError('Only the author or owner can edit complaint content.')
            if 'title' in data and data['title']:
                complaint.title = data['title'].strip()
            if 'description' in data and data['description']:
                complaint.description = data['description'].strip()
            if 'category' in data and data['category']:
                complaint.category = data['category']

        status_changed = False
        if 'status' in data:
            new_status = data['status']
            if not is_staff and new_status != ComplaintStatus.OPEN:
                raise ForbiddenError('Only owners or admins can change complaint status.')
            status_changed = complaint.status != new_status
            complaint.status = new_status
            if new_status == ComplaintStatus.RESOLVED:
                complaint.resolved_at = timezone.now()
            elif new_status != ComplaintStatus.RESOLVED:
                complaint.resolved_at = None

        replied = False
        if data.get('response'):
            if not is_staff and not is_creator:
                raise ForbiddenError('You cannot reply on this complaint.')
            reply = data['response'].strip()
            complaint.response = reply
            ComplaintMessage.objects.create(
                complaint=complaint,
                author=user,
                body=reply,
                is_staff_reply=is_staff,
            )
            replied = True

        complaint.save()
        from support.notify import schedule_complaint_reply, schedule_complaint_status

        if replied:
            schedule_complaint_reply(complaint.id, user.id, complaint.response)
        elif status_changed:
            schedule_complaint_status(complaint.id, user.id, complaint.status)

        complaint = _get_complaint(complaint.id)
        return Response(api_success(ComplaintSerializer(complaint).data))


class ComplaintMessageListCreateView(APIView):
    """Thread replies on a maintenance / complaint ticket."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        complaint = _get_complaint(pk)
        if not _can_access_complaint(request.user, complaint):
            raise ForbiddenError('You cannot view this complaint.')
        messages = complaint.messages.all().order_by('created_at')
        return Response(
            api_success(ComplaintMessageSerializer(messages, many=True).data),
        )

    def post(self, request, pk):
        complaint = _get_complaint(pk)
        if not _can_access_complaint(request.user, complaint):
            raise ForbiddenError('You cannot reply to this complaint.')
        if complaint.status == ComplaintStatus.RESOLVED:
            # Re-open on new message from either side
            complaint.status = ComplaintStatus.IN_PROGRESS
            complaint.resolved_at = None
            complaint.save(update_fields=['status', 'resolved_at', 'updated_at'])

        ser = ComplaintMessageCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        is_staff = request.user.role == Role.ADMIN or _is_managing_owner(
            request.user,
            complaint,
        )
        msg = ComplaintMessage.objects.create(
            complaint=complaint,
            author=request.user,
            body=ser.validated_data['body'].strip(),
            is_staff_reply=is_staff,
        )
        if is_staff:
            complaint.response = msg.body
            if complaint.status == ComplaintStatus.OPEN:
                complaint.status = ComplaintStatus.IN_PROGRESS
            complaint.save(update_fields=['response', 'status', 'updated_at'])

        from support.notify import schedule_complaint_reply

        schedule_complaint_reply(complaint.id, request.user.id, msg.body)

        return Response(
            api_success(ComplaintMessageSerializer(msg).data),
            status=status.HTTP_201_CREATED,
        )
