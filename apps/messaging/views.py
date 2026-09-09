from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from messaging.models import Chat, ChatMessage, MessageStatus, MessageType, Notification
from messaging.serializers import (
    ChatCreateSerializer,
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
    ChatSerializer,
    ChatUserSerializer,
    NotificationSerializer,
)


def _chat_qs():
    return Chat.objects.filter(is_deleted=False).select_related(
        'participant1',
        'participant2',
    )


def _get_chat(pk, user=None):
    try:
        chat = _chat_qs().get(pk=pk)
    except Chat.DoesNotExist as exc:
        raise NotFoundError('Chat not found.') from exc
    if user and user.id not in (chat.participant1_id, chat.participant2_id):
        raise ForbiddenError('You are not a participant in this chat.')
    return chat


def _user_chats(user):
    return _chat_qs().filter(
        Q(participant1=user) | Q(participant2=user),
    )


def _display_name(user):
    return user.name or f'User {user.phone[-4:]}'


def _avatar_url(user):
    if user.profile_photo:
        return user.profile_photo.url
    return ''


class ChatListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        chats = _user_chats(request.user).order_by('-last_message_time', '-updated_at')
        data = ChatSerializer(chats, many=True, context={'request': request}).data
        return Response(api_success(data))

    def post(self, request):
        ser = ChatCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        p2_id = data['participant2Id']

        if p2_id == request.user.id:
            raise InvalidError('Cannot create a chat with yourself.')

        try:
            p2 = User.objects.get(pk=p2_id, is_active=True)
        except User.DoesNotExist as exc:
            raise NotFoundError('Participant not found.') from exc

        p1, p2_ordered = sorted(
            [request.user, p2],
            key=lambda u: str(u.id),
        )

        chat = Chat.objects.filter(
            participant1=p1,
            participant2=p2_ordered,
            is_deleted=False,
        ).first()

        if not chat:
            chat = Chat.objects.create(
                participant1=p1,
                participant2=p2_ordered,
                participant1_name=_display_name(p1),
                participant2_name=_display_name(p2_ordered),
                participant1_avatar=_avatar_url(p1),
                participant2_avatar=_avatar_url(p2_ordered),
                property_id=data.get('propertyId'),
                property_name=data.get('propertyName', ''),
            )

        initial = data.get('initialMessage', '').strip()
        if initial:
            receiver = p2 if request.user.id == p1.id else p1
            msg = ChatMessage.objects.create(
                chat=chat,
                sender=request.user,
                receiver=receiver,
                type=MessageType.TEXT,
                content=initial,
                status=MessageStatus.SENT,
            )
            chat.last_message = initial
            chat.last_message_time = msg.created_at
            if receiver.id == chat.participant1_id:
                chat.unread_count_p1 += 1
            else:
                chat.unread_count_p2 += 1
            chat.save()

        return Response(
            api_success(ChatSerializer(chat, context={'request': request}).data),
            status=status.HTTP_201_CREATED,
        )


class ChatDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chat = _get_chat(pk, request.user)
        return Response(api_success(ChatSerializer(chat, context={'request': request}).data))


class ChatMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        chat = _get_chat(pk, request.user)
        messages = chat.messages.select_related('sender', 'receiver').order_by('created_at')

        to_deliver = messages.filter(
            receiver=request.user,
            status=MessageStatus.SENT,
        )
        to_deliver.update(status=MessageStatus.DELIVERED)

        if chat.participant1_id == request.user.id:
            chat.unread_count_p1 = 0
        else:
            chat.unread_count_p2 = 0
        chat.save(update_fields=['unread_count_p1', 'unread_count_p2', 'updated_at'])

        data = ChatMessageSerializer(messages, many=True).data
        return Response(api_success(data))

    def post(self, request, pk):
        chat = _get_chat(pk, request.user)
        ser = ChatMessageCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        other = chat.other_participant(request.user)
        receiver_id = data.get('receiverId') or other.id
        if receiver_id not in (chat.participant1_id, chat.participant2_id):
            raise InvalidError('Invalid receiver.')
        if receiver_id == request.user.id:
            raise InvalidError('Cannot send a message to yourself.')

        try:
            receiver = User.objects.get(pk=receiver_id)
        except User.DoesNotExist as exc:
            raise NotFoundError('Receiver not found.') from exc

        msg = ChatMessage.objects.create(
            chat=chat,
            sender=request.user,
            receiver=receiver,
            type=data.get('type', MessageType.TEXT),
            content=data['content'],
            file_name=data.get('fileName', ''),
            file_size=data.get('fileSize'),
            thumbnail=data.get('thumbnail', ''),
            status=MessageStatus.SENT,
        )

        chat.last_message = data['content'][:500]
        chat.last_message_time = msg.created_at
        if receiver.id == chat.participant1_id:
            chat.unread_count_p1 += 1
        else:
            chat.unread_count_p2 += 1
        chat.save()

        return Response(
            api_success(ChatMessageSerializer(msg).data),
            status=status.HTTP_201_CREATED,
        )


class ChatUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = ChatMessage.objects.filter(
            receiver=request.user,
            status__in=[MessageStatus.SENT, MessageStatus.DELIVERED],
        ).count()
        return Response(api_success({'count': count}))


class ChatUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist as exc:
            raise NotFoundError('User not found.') from exc

        data = ChatUserSerializer({
            'id': user.id,
            'name': _display_name(user),
            'phone': user.phone,
            'avatar': _avatar_url(user),
        }).data
        return Response(api_success(data))


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user).order_by('-created_at')
        return Response(api_success(NotificationSerializer(qs, many=True).data))


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist as exc:
            raise NotFoundError('Notification not found.') from exc
        notif.read = True
        notif.save(update_fields=['read', 'updated_at'])
        return Response(api_success(NotificationSerializer(notif).data))


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response(api_success({'updated': updated}))


class PushConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from messaging.services.push import (
            get_push_config,
            is_push_configured,
            should_send_push,
            vapid_public_key,
        )

        cfg = get_push_config()
        live = should_send_push(cfg)
        return Response(
            api_success(
                {
                    'enabled': live,
                    'configured': is_push_configured(),
                    'publicKey': vapid_public_key() if live else '',
                    'heartbeatEnabled': bool(cfg.get('heartbeatEnabled')),
                },
            ),
        )


class PushSubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.utils import timezone as dj_tz

        from messaging.models import PushSubscription

        endpoint = (request.data.get('endpoint') or '').strip()
        keys = request.data.get('keys') or {}
        p256dh = (keys.get('p256dh') or request.data.get('p256dh') or '').strip()
        auth = (keys.get('auth') or request.data.get('auth') or '').strip()
        if not endpoint or not p256dh or not auth:
            raise InvalidError('endpoint, keys.p256dh and keys.auth are required.')
        ua = (request.META.get('HTTP_USER_AGENT') or '')[:300]
        sub, _created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': ua,
                'last_seen_at': dj_tz.now(),
                'fail_count': 0,
            },
        )
        return Response(
            api_success({'id': str(sub.id), 'endpoint': sub.endpoint}),
            status=status.HTTP_201_CREATED,
        )

    def delete(self, request):
        from messaging.models import PushSubscription

        endpoint = (request.data.get('endpoint') or '').strip()
        if not endpoint:
            raise InvalidError('endpoint is required.')
        PushSubscription.objects.filter(
            user=request.user,
            endpoint=endpoint,
        ).delete()
        return Response(api_success({'removed': True}))


class PushTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from messaging.services.push import notify_user, should_send_push

        if not should_send_push():
            raise InvalidError(
                'Web push is off or VAPID keys are missing. Check admin settings and .env.',
            )
        result = notify_user(
            request.user,
            title='SmartBasa',
            body='Push notifications are working on this device.',
            url='/notifications',
            tag='push-test',
        )
        if result.get('sent', 0) < 1:
            raise InvalidError(
                'No active browser subscription. Allow notifications in this browser first.',
            )
        return Response(api_success(result))
