"""Unified notice API views."""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import ForbiddenError, NotFoundError
from core.scope import ScopeType
from ops.models import Notice, NoticeAck
from ops.serializers import NoticeSerializer, NoticeWriteSerializer
from ops.services import (
    assert_flat_targets_for_building,
    can_manage_scope,
    can_read_notice,
    notices_visible_to,
    resolve_scope_name,
)


def _get_notice(notice_id) -> Notice:
    try:
        return (
            Notice.objects.prefetch_related('acknowledgments')
            .get(pk=notice_id, is_deleted=False)
        )
    except Notice.DoesNotExist as exc:
        raise NotFoundError('Notice not found.') from exc


class UnifiedNoticeFeedView(APIView):
    """GET /notices/ — all scopes visible to the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (
            notices_visible_to(request.user)
            .prefetch_related('acknowledgments')
            .order_by('-date', '-created_at')
        )
        # Filter building flat-targeted notices for renters
        if request.user.role not in ('admin', 'owner'):
            filtered = [n for n in qs if can_read_notice(request.user, n)]
            return Response(
                api_success(NoticeSerializer(filtered, many=True).data),
            )
        return Response(api_success(NoticeSerializer(qs, many=True).data))


class UnifiedNoticeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notice_id):
        notice = _get_notice(notice_id)
        if not can_manage_scope(request.user, notice.scope_type, notice.scope_id):
            raise ForbiddenError('You cannot edit this notice.')
        ser = NoticeWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        if 'title' in data:
            notice.title = data['title']
        if 'content' in data:
            notice.content = data['content']
        if 'date' in data:
            notice.date = data['date']
        if 'priority' in data:
            notice.priority = data['priority']
        if 'category' in data:
            notice.category = data['category']
        if 'expiryDate' in data:
            notice.expiry_date = data.get('expiryDate')
        if 'pdfUrl' in data:
            notice.pdf_url = data.get('pdfUrl', '')
        if 'imageUrls' in data:
            notice.image_urls = data.get('imageUrls', [])
        targets = ser.resolved_target_ids() if (
            'targetIds' in request.data or 'flatIds' in request.data
        ) else None
        if targets is not None:
            if notice.scope_type == ScopeType.BUILDING:
                assert_flat_targets_for_building(notice.scope_id, targets)
            notice.target_ids = targets
        notice.save()
        notice = _get_notice(notice.id)
        return Response(api_success(NoticeSerializer(notice).data))

    def delete(self, request, notice_id):
        notice = _get_notice(notice_id)
        if not can_manage_scope(request.user, notice.scope_type, notice.scope_id):
            raise ForbiddenError('You cannot delete this notice.')
        notice.is_deleted = True
        notice.save(update_fields=['is_deleted', 'updated_at'])
        return Response(api_success({'deleted': True}))


class UnifiedNoticeAckView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notice_id):
        notice = _get_notice(notice_id)
        if not can_read_notice(request.user, notice):
            raise ForbiddenError('You cannot acknowledge this notice.')
        NoticeAck.objects.get_or_create(
            notice=notice,
            user=request.user,
            defaults={
                'acknowledged_at': timezone.now(),
                'user_name': request.user.name
                or f'User {request.user.phone[-4:]}',
            },
        )
        notice = _get_notice(notice.id)
        return Response(api_success(NoticeSerializer(notice).data))


class ScopeNoticeListCreateView(APIView):
    """
    GET/POST for a concrete scope.
    Used by /mess/<id>/notices/ and /buildings/<id>/notices/ and /hotels/<id>/notices/.
    """

    permission_classes = [IsAuthenticated]
    scope_type: str = ScopeType.MESS

    def get(self, request, scope_id):
        from ops.services import member_scope_ids

        is_owner = can_manage_scope(request.user, self.scope_type, scope_id)
        is_member = scope_id in member_scope_ids(request.user).get(
            self.scope_type,
            set(),
        )
        if not is_owner and not is_member and request.user.role != 'admin':
            raise ForbiddenError('You cannot view these notices.')
        qs = (
            Notice.objects.filter(
                scope_type=self.scope_type,
                scope_id=scope_id,
                is_deleted=False,
            )
            .prefetch_related('acknowledgments')
            .order_by('-date', '-created_at')
        )
        return Response(api_success(NoticeSerializer(qs, many=True).data))

    def post(self, request, scope_id):
        if not can_manage_scope(request.user, self.scope_type, scope_id):
            raise ForbiddenError('Only the owner can publish notices here.')
        ser = NoticeWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        targets = ser.resolved_target_ids()
        if self.scope_type == ScopeType.BUILDING:
            assert_flat_targets_for_building(scope_id, targets)
        notice = Notice.objects.create(
            scope_type=self.scope_type,
            scope_id=scope_id,
            scope_name=resolve_scope_name(self.scope_type, scope_id),
            target_ids=targets,
            title=data['title'],
            content=data['content'],
            date=data['date'],
            priority=data['priority'],
            category=data.get('category', 'general'),
            expiry_date=data.get('expiryDate'),
            pdf_url=data.get('pdfUrl', ''),
            image_urls=data.get('imageUrls', []),
            created_by=request.user,
        )
        from ops.notice_notify import schedule_notice_published

        schedule_notice_published(notice)
        return Response(
            api_success(NoticeSerializer(notice).data),
            status=status.HTTP_201_CREATED,
        )


class MessScopeNoticeView(ScopeNoticeListCreateView):
    scope_type = ScopeType.MESS

    def get(self, request, pk):
        return super().get(request, pk)

    def post(self, request, pk):
        return super().post(request, pk)


class BuildingScopeNoticeView(ScopeNoticeListCreateView):
    scope_type = ScopeType.BUILDING

    def get(self, request, building_id):
        return super().get(request, building_id)

    def post(self, request, building_id):
        return super().post(request, building_id)


class HotelScopeNoticeView(ScopeNoticeListCreateView):
    scope_type = ScopeType.HOTEL

    def get(self, request, hotel_id):
        return super().get(request, hotel_id)

    def post(self, request, hotel_id):
        return super().post(request, hotel_id)
