from rest_framework import serializers

from messaging.models import Chat, ChatMessage, Notification


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


class ChatSerializer(serializers.ModelSerializer):
    participant1Id = serializers.UUIDField(source='participant1_id', read_only=True)
    participant2Id = serializers.UUIDField(source='participant2_id', read_only=True)
    participant1Name = serializers.CharField(source='participant1_name')
    participant2Name = serializers.CharField(source='participant2_name')
    participant1Avatar = serializers.CharField(source='participant1_avatar', allow_blank=True)
    participant2Avatar = serializers.CharField(source='participant2_avatar', allow_blank=True)
    lastMessage = serializers.CharField(source='last_message', allow_blank=True)
    lastMessageTime = serializers.SerializerMethodField()
    unreadCount = serializers.SerializerMethodField()
    propertyId = serializers.SerializerMethodField()
    propertyName = serializers.CharField(source='property_name', allow_blank=True)
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = [
            'id',
            'participant1Id',
            'participant2Id',
            'participant1Name',
            'participant2Name',
            'participant1Avatar',
            'participant2Avatar',
            'lastMessage',
            'lastMessageTime',
            'unreadCount',
            'propertyId',
            'propertyName',
            'createdAt',
            'updatedAt',
        ]

    def get_lastMessageTime(self, obj) -> str | None:
        return _dt_str(obj.last_message_time)

    def get_propertyId(self, obj) -> str | None:
        return str(obj.property_id) if obj.property_id else None

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_updatedAt(self, obj) -> str:
        return _dt_str(obj.updated_at) or ''

    def get_unreadCount(self, obj) -> int:
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return obj.unread_for(user)
        return 0


class ChatMessageSerializer(serializers.ModelSerializer):
    chatId = serializers.UUIDField(source='chat_id', read_only=True)
    senderId = serializers.UUIDField(source='sender_id', read_only=True)
    receiverId = serializers.UUIDField(source='receiver_id', read_only=True)
    fileName = serializers.CharField(source='file_name', allow_blank=True)
    fileSize = serializers.IntegerField(source='file_size', allow_null=True)
    timestamp = serializers.SerializerMethodField()
    readAt = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'chatId',
            'senderId',
            'receiverId',
            'type',
            'content',
            'fileName',
            'fileSize',
            'thumbnail',
            'status',
            'timestamp',
            'readAt',
        ]

    def get_timestamp(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_readAt(self, obj) -> str | None:
        return _dt_str(obj.read_at)


class ChatCreateSerializer(serializers.Serializer):
    participant2Id = serializers.UUIDField()
    propertyId = serializers.UUIDField(required=False, allow_null=True)
    propertyName = serializers.CharField(required=False, allow_blank=True, default='')
    initialMessage = serializers.CharField(required=False, allow_blank=True, default='')


class ChatMessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField()
    type = serializers.ChoiceField(
        choices=['text', 'image', 'file', 'system'],
        required=False,
        default='text',
    )
    receiverId = serializers.UUIDField(required=False, allow_null=True)
    fileName = serializers.CharField(required=False, allow_blank=True, default='')
    fileSize = serializers.IntegerField(required=False, allow_null=True)
    thumbnail = serializers.URLField(required=False, allow_blank=True, default='')


class ChatUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    phone = serializers.CharField()
    avatar = serializers.CharField(required=False, allow_blank=True)


class NotificationSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'userId',
            'title',
            'message',
            'type',
            'read',
            'createdAt',
            'link',
        ]

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''
