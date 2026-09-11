from rest_framework import serializers

from core.scope import ScopeType
from hotels.models import Hotel
from mess.models import Mess
from portfolio.models import Building, Flat
from support.models import Complaint, ComplaintMessage


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


class ComplaintMessageSerializer(serializers.ModelSerializer):
    authorId = serializers.UUIDField(source='author_id', read_only=True)
    authorName = serializers.CharField(source='author_name', read_only=True)
    isStaffReply = serializers.BooleanField(source='is_staff_reply', read_only=True)
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintMessage
        fields = (
            'id',
            'authorId',
            'authorName',
            'body',
            'isStaffReply',
            'createdAt',
        )

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''


class ComplaintSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.CharField(source='user_name')
    imageUrl = serializers.CharField(source='image_url', allow_blank=True)
    scopeType = serializers.CharField(source='scope_type', read_only=True)
    scopeId = serializers.UUIDField(source='scope_id', read_only=True, allow_null=True)
    scopeName = serializers.CharField(source='scope_name', read_only=True)
    targetId = serializers.UUIDField(source='target_id', read_only=True, allow_null=True)
    targetLabel = serializers.CharField(source='target_label', read_only=True)
    buildingId = serializers.UUIDField(source='building_id', read_only=True, allow_null=True)
    flatId = serializers.UUIDField(source='flat_id', read_only=True, allow_null=True)
    flatNumber = serializers.SerializerMethodField()
    buildingName = serializers.SerializerMethodField()
    messages = ComplaintMessageSerializer(many=True, read_only=True)
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()
    resolvedAt = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = [
            'id',
            'userId',
            'userName',
            'title',
            'description',
            'status',
            'category',
            'imageUrl',
            'scopeType',
            'scopeId',
            'scopeName',
            'targetId',
            'targetLabel',
            'buildingId',
            'buildingName',
            'flatId',
            'flatNumber',
            'createdAt',
            'updatedAt',
            'resolvedAt',
            'response',
            'messages',
        ]

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_updatedAt(self, obj) -> str:
        return _dt_str(obj.updated_at) or ''

    def get_resolvedAt(self, obj) -> str | None:
        return _dt_str(obj.resolved_at)

    def get_flatNumber(self, obj) -> str | None:
        if obj.target_label:
            return obj.target_label
        if obj.flat_id and getattr(obj, 'flat', None):
            return obj.flat.flat_number
        return None

    def get_buildingName(self, obj) -> str | None:
        if obj.scope_name:
            return obj.scope_name
        if obj.building_id and getattr(obj, 'building', None):
            return obj.building.name
        return None


class ComplaintCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    imageUrl = serializers.URLField(required=False, allow_blank=True, default='')
    category = serializers.ChoiceField(
        choices=['maintenance', 'billing', 'noise', 'other'],
        required=False,
        default='maintenance',
    )
    scopeType = serializers.ChoiceField(
        choices=ScopeType.choices,
        required=False,
        allow_blank=True,
    )
    scopeId = serializers.UUIDField(required=False, allow_null=True)
    targetId = serializers.UUIDField(required=False, allow_null=True)
    # Legacy aliases
    buildingId = serializers.UUIDField(required=False, allow_null=True)
    flatId = serializers.UUIDField(required=False, allow_null=True)
    messId = serializers.UUIDField(required=False, allow_null=True)
    hotelId = serializers.UUIDField(required=False, allow_null=True)

    def create_complaint(self, user):
        name = user.name or f'User {user.phone[-4:]}'
        data = self.validated_data
        flat = None
        building = None
        scope_type = data.get('scopeType') or ''
        scope_id = data.get('scopeId')
        target_id = data.get('targetId') or data.get('flatId')
        target_label = ''
        scope_name = ''

        # Resolve aliases
        if data.get('messId'):
            scope_type = ScopeType.MESS
            scope_id = data['messId']
        elif data.get('hotelId'):
            scope_type = ScopeType.HOTEL
            scope_id = data['hotelId']
        elif data.get('flatId') or data.get('buildingId'):
            scope_type = ScopeType.BUILDING
            flat_id = data.get('flatId')
            building_id = data.get('buildingId')
            if flat_id:
                flat = Flat.objects.select_related('building').filter(pk=flat_id).first()
                if flat:
                    building = flat.building
                    scope_id = building.id
                    target_id = flat.id
                    target_label = flat.flat_number
                    scope_name = building.name
            elif building_id:
                building = Building.objects.filter(pk=building_id).first()
                if building:
                    scope_id = building.id
                    scope_name = building.name

        if scope_type == ScopeType.MESS and scope_id:
            mess = Mess.objects.filter(pk=scope_id).first()
            scope_name = mess.name if mess else ''
        elif scope_type == ScopeType.HOTEL and scope_id:
            hotel = Hotel.objects.filter(pk=scope_id).first()
            scope_name = hotel.name if hotel else ''
        elif scope_type == ScopeType.BUILDING and scope_id and not building:
            building = Building.objects.filter(pk=scope_id).first()
            if building:
                scope_name = building.name
            if target_id and not flat:
                flat = Flat.objects.filter(pk=target_id).first()
                if flat:
                    target_label = flat.flat_number

        complaint = Complaint.objects.create(
            user=user,
            user_name=name,
            title=data['title'],
            description=data['description'],
            image_url=data.get('imageUrl', ''),
            category=data.get('category', 'maintenance'),
            scope_type=scope_type or '',
            scope_id=scope_id,
            scope_name=scope_name,
            target_id=target_id,
            target_label=target_label,
            building=building,
            flat=flat,
        )
        ComplaintMessage.objects.create(
            complaint=complaint,
            author=user,
            author_name=name,
            body=data['description'],
            is_staff_reply=False,
        )
        return complaint


class ComplaintStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['open', 'in_progress', 'resolved'],
        required=False,
    )
    response = serializers.CharField(required=False, allow_blank=True, default='')
    title = serializers.CharField(required=False, max_length=255)
    description = serializers.CharField(required=False)
    category = serializers.ChoiceField(
        choices=['maintenance', 'billing', 'noise', 'other'],
        required=False,
    )


class ComplaintMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=1, max_length=4000)
