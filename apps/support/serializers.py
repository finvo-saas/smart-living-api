from rest_framework import serializers

from portfolio.models import Flat
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
        if obj.flat_id and getattr(obj, 'flat', None):
            return obj.flat.flat_number
        return None

    def get_buildingName(self, obj) -> str | None:
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
    buildingId = serializers.UUIDField(required=False, allow_null=True)
    flatId = serializers.UUIDField(required=False, allow_null=True)

    def create_complaint(self, user):
        name = user.name or f'User {user.phone[-4:]}'
        flat = None
        building = None
        flat_id = self.validated_data.get('flatId')
        building_id = self.validated_data.get('buildingId')
        if flat_id:
            flat = Flat.objects.select_related('building').filter(pk=flat_id).first()
            if flat:
                building = flat.building
        elif building_id:
            from portfolio.models import Building

            building = Building.objects.filter(pk=building_id).first()

        complaint = Complaint.objects.create(
            user=user,
            user_name=name,
            title=self.validated_data['title'],
            description=self.validated_data['description'],
            image_url=self.validated_data.get('imageUrl', ''),
            category=self.validated_data.get('category', 'maintenance'),
            building=building,
            flat=flat,
        )
        # Seed thread with the original description
        ComplaintMessage.objects.create(
            complaint=complaint,
            author=user,
            author_name=name,
            body=self.validated_data['description'],
            is_staff_reply=False,
        )
        return complaint


class ComplaintStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['open', 'in_progress', 'resolved'])
    response = serializers.CharField(required=False, allow_blank=True, default='')


class ComplaintMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=1, max_length=4000)
