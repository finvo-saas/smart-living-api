"""Building notice API views."""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from portfolio.models import (
    Building,
    BuildingNotice,
    BuildingNoticeAck,
    Flat,
    Tenancy,
    TenancyStatus,
)
from portfolio.serializers_notices import (
    BuildingNoticeSerializer,
    BuildingNoticeWriteSerializer,
)


def _owner_building(user, building_id) -> Building:
    try:
        building = Building.objects.get(pk=building_id)
    except Building.DoesNotExist as exc:
        raise NotFoundError('Building not found.') from exc
    if building.owner_id != user.id and user.role != Role.ADMIN:
        raise ForbiddenError('You can only manage your own buildings.')
    return building


def _get_notice(notice_id) -> BuildingNotice:
    try:
        return (
            BuildingNotice.objects.select_related('building')
            .prefetch_related('acknowledgments')
            .get(pk=notice_id, is_deleted=False)
        )
    except BuildingNotice.DoesNotExist as exc:
        raise NotFoundError('Notice not found.') from exc


def _can_read_notice(user, notice: BuildingNotice) -> bool:
    if user.role == Role.ADMIN:
        return True
    if notice.building.owner_id == user.id:
        return True
    tenancies = Tenancy.objects.filter(
        tenant=user,
        status=TenancyStatus.ACTIVE,
        flat__building_id=notice.building_id,
    ).select_related('flat')
    if not tenancies.exists():
        return False
    flat_ids = notice.flat_ids or []
    if not flat_ids:
        return True
    flat_id_strs = {str(f) for f in flat_ids}
    return any(str(t.flat_id) in flat_id_strs for t in tenancies)


class BuildingNoticeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, building_id):
        building = _owner_building(request.user, building_id)
        qs = (
            BuildingNotice.objects.filter(building=building, is_deleted=False)
            .prefetch_related('acknowledgments')
            .order_by('-date', '-created_at')
        )
        return Response(
            api_success(BuildingNoticeSerializer(qs, many=True).data),
        )

    def post(self, request, building_id):
        building = _owner_building(request.user, building_id)
        ser = BuildingNoticeWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        flat_ids = [str(fid) for fid in (data.get('flatIds') or [])]
        if flat_ids:
            owned = set(
                str(fid)
                for fid in Flat.objects.filter(
                    building=building,
                    id__in=flat_ids,
                ).values_list('id', flat=True)
            )
            if set(flat_ids) - owned:
                raise InvalidError('One or more flats do not belong to this building.')
        notice = BuildingNotice.objects.create(
            building=building,
            title=data['title'],
            content=data['content'],
            date=data['date'],
            priority=data['priority'],
            category=data.get('category', 'general'),
            expiry_date=data.get('expiryDate'),
            pdf_url=data.get('pdfUrl', ''),
            image_urls=data.get('imageUrls', []),
            flat_ids=flat_ids,
            created_by=request.user,
        )
        return Response(
            api_success(BuildingNoticeSerializer(notice).data),
            status=status.HTTP_201_CREATED,
        )


class BuildingNoticeFeedView(APIView):
    """GET /building-notices/ — owner buildings + renter tenancy buildings."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == Role.ADMIN:
            qs = BuildingNotice.objects.filter(is_deleted=False)
        elif user.role == Role.OWNER:
            qs = BuildingNotice.objects.filter(
                building__owner=user,
                is_deleted=False,
            )
        else:
            tenancies = list(
                Tenancy.objects.filter(
                    tenant=user,
                    status=TenancyStatus.ACTIVE,
                ).select_related('flat'),
            )
            building_ids = {t.flat.building_id for t in tenancies}
            qs = BuildingNotice.objects.filter(
                building_id__in=building_ids,
                is_deleted=False,
            )
            # Filter flat-targeted notices in Python for simplicity
            flat_by_building: dict = {}
            for t in tenancies:
                flat_by_building.setdefault(t.flat.building_id, set()).add(str(t.flat_id))
            filtered = []
            for notice in qs.select_related('building').prefetch_related('acknowledgments'):
                targets = notice.flat_ids or []
                if not targets:
                    filtered.append(notice)
                    continue
                my_flats = flat_by_building.get(notice.building_id, set())
                if my_flats & {str(f) for f in targets}:
                    filtered.append(notice)
            return Response(
                api_success(BuildingNoticeSerializer(filtered, many=True).data),
            )

        qs = qs.select_related('building').prefetch_related('acknowledgments').order_by(
            '-date',
            '-created_at',
        )
        return Response(api_success(BuildingNoticeSerializer(qs, many=True).data))


class BuildingNoticeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notice_id):
        notice = _get_notice(notice_id)
        if notice.building.owner_id != request.user.id and request.user.role != Role.ADMIN:
            raise ForbiddenError('Only the building owner can edit notices.')
        ser = BuildingNoticeWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        field_map = {
            'title': 'title',
            'content': 'content',
            'date': 'date',
            'priority': 'priority',
            'category': 'category',
            'expiryDate': 'expiry_date',
            'pdfUrl': 'pdf_url',
            'imageUrls': 'image_urls',
            'flatIds': 'flat_ids',
        }
        updates = []
        for key, attr in field_map.items():
            if key in data:
                value = data[key]
                if key == 'flatIds':
                    value = [str(v) for v in (value or [])]
                setattr(notice, attr, value)
                updates.append(attr)
        if updates:
            notice.save(update_fields=updates + ['updated_at'])
        return Response(api_success(BuildingNoticeSerializer(notice).data))

    def delete(self, request, notice_id):
        notice = _get_notice(notice_id)
        if notice.building.owner_id != request.user.id and request.user.role != Role.ADMIN:
            raise ForbiddenError('Only the building owner can delete notices.')
        notice.is_deleted = True
        notice.save(update_fields=['is_deleted', 'updated_at'])
        return Response(api_success(None))


class BuildingNoticeAckView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notice_id):
        notice = _get_notice(notice_id)
        if not _can_read_notice(request.user, notice):
            raise ForbiddenError('You cannot acknowledge this notice.')
        ack, _created = BuildingNoticeAck.objects.get_or_create(
            notice=notice,
            user=request.user,
            defaults={
                'acknowledged_at': timezone.now(),
                'user_name': request.user.name
                or f'User {request.user.phone[-4:]}',
            },
        )
        return Response(
            api_success(BuildingNoticeSerializer(notice).data),
            status=status.HTTP_200_OK if not _created else status.HTTP_201_CREATED,
        )
