"""Serializers for unified ops.Notice."""

from rest_framework import serializers

from core.scope import ScopeType
from ops.models import Notice, NoticeAck, NoticeCategory, NoticePriority


class NoticeAckSerializer(serializers.Serializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.CharField(source='user_name', read_only=True)
    acknowledgedAt = serializers.DateTimeField(source='acknowledged_at', read_only=True)


class NoticeSerializer(serializers.ModelSerializer):
    scopeType = serializers.CharField(source='scope_type', read_only=True)
    scopeId = serializers.UUIDField(source='scope_id', read_only=True)
    scopeName = serializers.CharField(source='scope_name', read_only=True)
    targetIds = serializers.JSONField(source='target_ids', required=False)
    # FE compatibility with prior mess / building payloads
    messId = serializers.SerializerMethodField()
    buildingId = serializers.SerializerMethodField()
    buildingName = serializers.SerializerMethodField()
    flatIds = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()
    expiryDate = serializers.DateField(source='expiry_date', allow_null=True, required=False)
    pdfUrl = serializers.CharField(source='pdf_url', allow_blank=True, required=False)
    imageUrls = serializers.JSONField(source='image_urls', required=False)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    acknowledgments = NoticeAckSerializer(many=True, read_only=True)

    class Meta:
        model = Notice
        fields = (
            'id',
            'title',
            'content',
            'date',
            'priority',
            'category',
            'scopeType',
            'scopeId',
            'scopeName',
            'targetIds',
            'messId',
            'buildingId',
            'buildingName',
            'flatIds',
            'source',
            'expiryDate',
            'pdfUrl',
            'imageUrls',
            'createdBy',
            'createdAt',
            'acknowledgments',
        )

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''

    def get_source(self, obj):
        return obj.scope_type

    def get_messId(self, obj):
        if obj.scope_type == ScopeType.MESS:
            return str(obj.scope_id)
        return None

    def get_buildingId(self, obj):
        if obj.scope_type == ScopeType.BUILDING:
            return str(obj.scope_id)
        return None

    def get_buildingName(self, obj):
        if obj.scope_type == ScopeType.BUILDING:
            return obj.scope_name or None
        return None

    def get_flatIds(self, obj):
        if obj.scope_type == ScopeType.BUILDING:
            return obj.target_ids or []
        return []


class NoticeWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    date = serializers.DateField()
    priority = serializers.ChoiceField(choices=NoticePriority.choices)
    category = serializers.ChoiceField(
        choices=NoticeCategory.choices,
        required=False,
        default=NoticeCategory.GENERAL,
    )
    expiryDate = serializers.DateField(required=False, allow_null=True)
    pdfUrl = serializers.CharField(required=False, allow_blank=True, default='')
    imageUrls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    targetIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    # Legacy aliases
    flatIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    def resolved_target_ids(self):
        data = self.validated_data
        targets = data.get('targetIds') or data.get('flatIds') or []
        return [str(t) for t in targets]
