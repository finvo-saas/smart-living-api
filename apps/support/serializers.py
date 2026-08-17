from rest_framework import serializers

from support.models import Complaint


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


class ComplaintSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.CharField(source='user_name')
    imageUrl = serializers.CharField(source='image_url', allow_blank=True)
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
            'imageUrl',
            'createdAt',
            'updatedAt',
            'resolvedAt',
            'response',
        ]

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_updatedAt(self, obj) -> str:
        return _dt_str(obj.updated_at) or ''

    def get_resolvedAt(self, obj) -> str | None:
        return _dt_str(obj.resolved_at)


class ComplaintCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    imageUrl = serializers.URLField(required=False, allow_blank=True, default='')

    def create_complaint(self, user):
        name = user.name or f'User {user.phone[-4:]}'
        return Complaint.objects.create(
            user=user,
            user_name=name,
            title=self.validated_data['title'],
            description=self.validated_data['description'],
            image_url=self.validated_data.get('imageUrl', ''),
        )


class ComplaintStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['open', 'in_progress', 'resolved'])
    response = serializers.CharField(required=False, allow_blank=True, default='')
