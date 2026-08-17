from rest_framework import serializers

from audit.models import AuditLog


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


class AuditLogSerializer(serializers.ModelSerializer):
    userId = serializers.SerializerMethodField()
    userName = serializers.CharField(source='user_name', read_only=True)
    userRole = serializers.CharField(source='user_role', read_only=True)
    entityType = serializers.CharField(source='entity_type', read_only=True)
    entityId = serializers.CharField(source='entity_id', read_only=True)
    entityName = serializers.CharField(source='entity_name', read_only=True)
    ipAddress = serializers.CharField(source='ip_address', read_only=True, allow_null=True)
    userAgent = serializers.CharField(source='user_agent', read_only=True)
    rollbackData = serializers.JSONField(source='rollback_data', read_only=True)
    canRollback = serializers.BooleanField(source='can_rollback', read_only=True)
    timestamp = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'action',
            'entityType',
            'entityId',
            'entityName',
            'userId',
            'userName',
            'userRole',
            'timestamp',
            'ipAddress',
            'userAgent',
            'changes',
            'metadata',
            'rollbackData',
            'canRollback',
        ]

    def get_userId(self, obj) -> str | None:
        if obj.user_id:
            return str(obj.user_id)
        return None

    def get_timestamp(self, obj) -> str:
        return _dt_str(obj.created_at) or ''


class AuditLogCreateSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[
            'create', 'update', 'delete', 'approve', 'reject',
            'verify', 'unverify', 'payment', 'rollback',
        ],
    )
    entityType = serializers.CharField()
    entityId = serializers.CharField()
    entityName = serializers.CharField(required=False, allow_blank=True, default='')
    changes = serializers.ListField(required=False, default=list)
    metadata = serializers.DictField(required=False, default=dict)
    rollbackData = serializers.DictField(required=False, allow_null=True, default=None)
    canRollback = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        return {
            'action': attrs['action'],
            'entity_type': attrs['entityType'],
            'entity_id': attrs['entityId'],
            'entity_name': attrs.get('entityName', ''),
            'changes': attrs.get('changes') or [],
            'metadata': attrs.get('metadata') or {},
            'rollback_data': attrs.get('rollbackData'),
            'can_rollback': attrs.get('canRollback', False),
        }
