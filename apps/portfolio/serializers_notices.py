"""Building notice serializers (apartment tenants)."""

from rest_framework import serializers

from portfolio.models import BuildingNotice


class BuildingNoticeAckSerializer(serializers.Serializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.CharField(source='user_name', read_only=True)
    acknowledgedAt = serializers.DateTimeField(source='acknowledged_at', read_only=True)


class BuildingNoticeSerializer(serializers.ModelSerializer):
    buildingId = serializers.UUIDField(source='building_id', read_only=True)
    buildingName = serializers.CharField(source='building.name', read_only=True)
    flatIds = serializers.JSONField(source='flat_ids', required=False)
    expiryDate = serializers.DateField(source='expiry_date', allow_null=True, required=False)
    pdfUrl = serializers.CharField(source='pdf_url', allow_blank=True, required=False)
    imageUrls = serializers.JSONField(source='image_urls', required=False)
    createdBy = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    acknowledgments = BuildingNoticeAckSerializer(many=True, read_only=True)
    source = serializers.SerializerMethodField()

    class Meta:
        model = BuildingNotice
        fields = (
            'id',
            'title',
            'content',
            'date',
            'priority',
            'buildingId',
            'buildingName',
            'flatIds',
            'category',
            'expiryDate',
            'pdfUrl',
            'imageUrls',
            'createdBy',
            'createdAt',
            'acknowledgments',
            'source',
        )

    def get_createdBy(self, obj):
        return str(obj.created_by_id) if obj.created_by_id else ''

    def get_source(self, obj):
        return 'building'


class BuildingNoticeWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    date = serializers.DateField()
    priority = serializers.ChoiceField(choices=['high', 'medium', 'low'])
    category = serializers.ChoiceField(
        choices=[
            'general',
            'payment',
            'maintenance',
            'event',
            'announcement',
            'rule',
            'other',
        ],
        required=False,
        default='general',
    )
    expiryDate = serializers.DateField(required=False, allow_null=True)
    pdfUrl = serializers.CharField(required=False, allow_blank=True, default='')
    imageUrls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    flatIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
