"""Server-Sent Events for live status, chat, and booking updates."""
from __future__ import annotations

import json
import time
from datetime import timedelta

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from core.exceptions import ForbiddenError, NotFoundError


def _sse(event: str, data: dict) -> str:
    return f'event: {event}\ndata: {json.dumps(data, default=str)}\n\n'


class MessLiveStatusSSEView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        from mess.models import Mess
        from mess.services.live_status import serialize_live_status

        try:
            Mess.objects.get(pk=pk, is_deleted=False)
        except Mess.DoesNotExist as exc:
            raise NotFoundError('Mess not found.') from exc

        def stream():
            last = None
            for _ in range(60):
                mess = Mess.objects.get(pk=pk)
                payload = serialize_live_status(mess)
                stamp = payload.get('updatedAt')
                if stamp != last:
                    last = stamp
                    yield _sse('live_status', payload)
                else:
                    yield _sse('ping', {'t': timezone.now().isoformat()})
                time.sleep(2)

        response = StreamingHttpResponse(stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ChatMessagesSSEView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from messaging.models import Chat, ChatMessage
        from messaging.serializers import ChatMessageSerializer

        try:
            chat = Chat.objects.get(pk=pk, is_deleted=False)
        except Chat.DoesNotExist as exc:
            raise NotFoundError('Chat not found.') from exc
        if request.user.id not in (chat.participant1_id, chat.participant2_id):
            if getattr(request.user, 'role', None) != 'admin':
                raise ForbiddenError('Access denied.')

        def stream():
            seen = set()
            for _ in range(45):
                cutoff = timezone.now() - timedelta(seconds=30)
                rows = list(
                    ChatMessage.objects.filter(chat=chat, created_at__gte=cutoff)
                    .select_related('sender', 'receiver')
                    .order_by('created_at')[:40],
                )
                fresh = [m for m in rows if str(m.id) not in seen]
                for m in fresh:
                    seen.add(str(m.id))
                if fresh:
                    yield _sse(
                        'messages',
                        {'messages': ChatMessageSerializer(fresh, many=True).data},
                    )
                else:
                    yield _sse('ping', {'t': timezone.now().isoformat()})
                time.sleep(2)

        response = StreamingHttpResponse(stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class BookingUpdatesSSEView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from bookings.models import PropertyBooking
        from bookings.serializers import PropertyBookingSerializer

        user = request.user

        def stream():
            last_stamp = None
            for _ in range(45):
                qs = PropertyBooking.objects.filter(is_deleted=False)
                role = getattr(user, 'role', None)
                if role == 'owner':
                    qs = qs.filter(owner=user)
                elif role != 'admin':
                    qs = qs.filter(renter=user)
                latest = qs.order_by('-updated_at').first()
                stamp = latest.updated_at.isoformat() if latest else None
                if stamp != last_stamp:
                    last_stamp = stamp
                    rows = list(qs.order_by('-updated_at')[:10])
                    yield _sse(
                        'bookings',
                        {
                            'bookings': PropertyBookingSerializer(
                                rows,
                                many=True,
                                context={'request': request},
                            ).data,
                            'updatedAt': stamp,
                        },
                    )
                else:
                    yield _sse('ping', {'t': timezone.now().isoformat()})
                time.sleep(3)

        response = StreamingHttpResponse(stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
