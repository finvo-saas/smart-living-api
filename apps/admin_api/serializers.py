from rest_framework import serializers

from accounts.models import AdminProfile, User, VerificationDocument
from admin_api.models import ActivityLog, Dispute, FraudReport, SystemSettings
from admin_api.services import map_listing_to_moderation_status, map_verification_status
from listings.models import Property


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


class AdminUserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='admin_profile.admin_role', read_only=True)
    createdAt = serializers.SerializerMethodField()
    lastLogin = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='admin_profile.is_active', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'phone', 'role', 'createdAt', 'lastLogin', 'isActive']

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_lastLogin(self, obj) -> str | None:
        return _dt_str(obj.last_login)


class DisputeSerializer(serializers.ModelSerializer):
    createdBy = serializers.UUIDField(source='created_by_id', read_only=True)
    createdByName = serializers.CharField(source='created_by_name', read_only=True)
    assignedTo = serializers.SerializerMethodField()
    assignedToName = serializers.CharField(source='assigned_to_name', read_only=True)
    relatedUserId = serializers.SerializerMethodField()
    relatedPropertyId = serializers.SerializerMethodField()
    relatedBookingId = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()
    resolvedAt = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = [
            'id', 'title', 'description', 'type', 'status', 'priority',
            'createdBy', 'createdByName', 'assignedTo', 'assignedToName',
            'relatedUserId', 'relatedPropertyId', 'relatedBookingId',
            'evidence', 'resolution', 'createdAt', 'updatedAt', 'resolvedAt',
        ]

    def get_assignedTo(self, obj) -> str | None:
        return str(obj.assigned_to_id) if obj.assigned_to_id else None

    def get_relatedUserId(self, obj) -> str | None:
        return str(obj.related_user_id) if obj.related_user_id else None

    def get_relatedPropertyId(self, obj) -> str | None:
        return str(obj.related_property_id) if obj.related_property_id else None

    def get_relatedBookingId(self, obj) -> str | None:
        return str(obj.related_booking_id) if obj.related_booking_id else None

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_updatedAt(self, obj) -> str:
        return _dt_str(obj.updated_at) or ''

    def get_resolvedAt(self, obj) -> str | None:
        return _dt_str(obj.resolved_at)


class DisputeCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    type = serializers.ChoiceField(
        choices=['payment', 'property', 'booking', 'other'],
        default='other',
    )
    priority = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'urgent'],
        default='medium',
    )
    relatedUserId = serializers.UUIDField(required=False, allow_null=True)
    relatedPropertyId = serializers.UUIDField(required=False, allow_null=True)
    relatedBookingId = serializers.UUIDField(required=False, allow_null=True)
    evidence = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class DisputePatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['open', 'assigned', 'in_progress', 'resolved', 'closed'],
        required=False,
    )
    assignedTo = serializers.UUIDField(required=False, allow_null=True)
    resolution = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'urgent'],
        required=False,
    )


class FraudReportSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.CharField(source='user_name', read_only=True)
    reportType = serializers.CharField(source='report_type', read_only=True)
    reportedAt = serializers.SerializerMethodField()
    investigatedBy = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    class Meta:
        model = FraudReport
        fields = [
            'id', 'userId', 'userName', 'reportType', 'description', 'evidence',
            'status', 'reportedAt', 'investigatedBy', 'resolution', 'priority',
            'updatedAt',
        ]

    def get_reportedAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_investigatedBy(self, obj) -> str | None:
        return str(obj.investigated_by_id) if obj.investigated_by_id else None

    def get_updatedAt(self, obj) -> str:
        return _dt_str(obj.updated_at) or ''


class FraudReportCreateSerializer(serializers.Serializer):
    userId = serializers.UUIDField()
    reportType = serializers.ChoiceField(
        choices=['suspicious_activity', 'fake_listing', 'payment_fraud', 'other'],
    )
    description = serializers.CharField()
    evidence = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    priority = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'urgent'],
        default='medium',
    )


class FraudReportPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['pending', 'investigating', 'resolved', 'dismissed'],
        required=False,
    )
    resolution = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'urgent'],
        required=False,
    )
    investigatedBy = serializers.UUIDField(required=False, allow_null=True)


class ActivityLogSerializer(serializers.ModelSerializer):
    userId = serializers.SerializerMethodField()
    userName = serializers.CharField(source='user_name', read_only=True)
    resourceType = serializers.CharField(source='resource_type', read_only=True)
    resourceId = serializers.CharField(source='resource_id', read_only=True)
    ipAddress = serializers.CharField(source='ip_address', read_only=True, allow_null=True)
    userAgent = serializers.CharField(source='user_agent', read_only=True)
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = [
            'id', 'userId', 'userName', 'action', 'resourceType', 'resourceId',
            'details', 'ipAddress', 'userAgent', 'createdAt',
        ]

    def get_userId(self, obj) -> str | None:
        return str(obj.user_id) if obj.user_id else None

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''


class SystemSettingsSerializer(serializers.ModelSerializer):
    platformName = serializers.CharField(source='platform_name')
    platformEmail = serializers.EmailField(source='platform_email')
    platformPhone = serializers.CharField(source='platform_phone')
    commissionRate = serializers.FloatField(source='commission_rate')
    subscriptionPlans = serializers.JSONField(source='subscription_plans')
    featureFlags = serializers.JSONField(source='feature_flags')
    smsGateway = serializers.JSONField(source='sms_gateway')
    emailService = serializers.JSONField(source='email_service')
    heartbeat = serializers.JSONField(required=False)
    push = serializers.JSONField(required=False)

    class Meta:
        model = SystemSettings
        fields = [
            'platformName', 'platformEmail', 'platformPhone', 'commissionRate',
            'subscriptionPlans', 'featureFlags', 'smsGateway', 'emailService',
            'heartbeat', 'push',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        from discovery.services.heartbeat import merge_heartbeat_config
        from messaging.services.push import merge_push_config

        data['heartbeat'] = merge_heartbeat_config(instance.heartbeat or {})
        data['push'] = merge_push_config(instance.push or {})
        return data

    def validate_heartbeat(self, value):
        from discovery.services.heartbeat import merge_heartbeat_config

        if value is None:
            return merge_heartbeat_config({})
        if not isinstance(value, dict):
            raise serializers.ValidationError('heartbeat must be an object.')
        return merge_heartbeat_config(value)

    def validate_push(self, value):
        from messaging.services.push import merge_push_config

        if value is None:
            return merge_push_config({})
        if not isinstance(value, dict):
            raise serializers.ValidationError('push must be an object.')
        return merge_push_config(value)


class VerificationRequestSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.SerializerMethodField()
    userEmail = serializers.SerializerMethodField()
    userPhone = serializers.SerializerMethodField()
    verificationType = serializers.CharField(source='verification_type', read_only=True)
    documentNumber = serializers.CharField(source='document_number', read_only=True)
    documentImage = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    submittedAt = serializers.SerializerMethodField()
    reviewedAt = serializers.SerializerMethodField()
    reviewedBy = serializers.SerializerMethodField()
    rejectionReason = serializers.CharField(source='rejection_reason', read_only=True)
    notes = serializers.SerializerMethodField()

    class Meta:
        model = VerificationDocument
        fields = [
            'id', 'userId', 'userName', 'userEmail', 'userPhone', 'verificationType',
            'documentNumber', 'documentImage', 'status', 'submittedAt', 'reviewedAt',
            'reviewedBy', 'rejectionReason', 'notes',
        ]

    def get_userName(self, obj) -> str:
        return obj.user.name or obj.user.phone

    def get_userEmail(self, obj) -> str:
        return obj.user.email or ''

    def get_userPhone(self, obj) -> str:
        return obj.user.phone

    def get_documentImage(self, obj) -> str | None:
        if not obj.file:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

    def get_status(self, obj) -> str:
        return map_verification_status(obj.status)

    def get_submittedAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_reviewedAt(self, obj) -> str | None:
        return _dt_str(obj.reviewed_at)

    def get_reviewedBy(self, obj) -> str | None:
        return str(obj.reviewed_by_id) if obj.reviewed_by_id else None

    def get_notes(self, obj) -> str:
        return ''


class VerificationPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['approved', 'rejected'])
    rejectionReason = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class PropertyModerationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    propertyId = serializers.UUIDField()
    propertyType = serializers.CharField()
    propertyName = serializers.CharField()
    ownerId = serializers.UUIDField()
    ownerName = serializers.CharField()
    status = serializers.CharField()
    submittedAt = serializers.CharField()
    reviewedAt = serializers.CharField(required=False, allow_null=True)
    reviewedBy = serializers.CharField(required=False, allow_null=True)
    rejectionReason = serializers.CharField(required=False, allow_blank=True)
    featured = serializers.BooleanField()
    verified = serializers.BooleanField()
    city = serializers.CharField()
    area = serializers.CharField()
    rent = serializers.FloatField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    imageUrl = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    @staticmethod
    def from_property(prop: Property) -> dict:
        owner = prop.owner
        prop_type = prop.type
        if prop_type == 'hostel':
            prop_type = 'apartment'
        image_url = None
        if isinstance(prop.image_urls, list) and prop.image_urls:
            image_url = prop.image_urls[0]
        if not image_url:
            first_image = prop.image_files.order_by('sort_order', 'created_at').first()
            if first_image:
                image_url = first_image.resolved_url() or None
        return {
            'id': prop.id,
            'propertyId': prop.id,
            'propertyType': prop_type,
            'propertyName': prop.name,
            'ownerId': owner.id,
            'ownerName': owner.name or owner.phone,
            'status': map_listing_to_moderation_status(prop),
            'submittedAt': _dt_str(prop.created_at) or '',
            'reviewedAt': _dt_str(prop.verified_at),
            'reviewedBy': None,
            'rejectionReason': '',
            'featured': prop.featured,
            'verified': prop.verified,
            'city': prop.city,
            'area': prop.area,
            'rent': float(prop.rent) if prop.rent is not None else 0,
            'description': prop.description or '',
            'imageUrl': image_url,
        }


class PropertyModerationPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['pending', 'approved', 'rejected', 'suspended'],
        required=False,
    )
    rejectionReason = serializers.CharField(required=False, allow_blank=True, default='')
    featured = serializers.BooleanField(required=False)
    verified = serializers.BooleanField(required=False)


class UserManagementSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.CharField()
    phone = serializers.CharField()
    role = serializers.CharField()
    status = serializers.CharField()
    verified = serializers.BooleanField()
    createdAt = serializers.CharField()
    lastLogin = serializers.CharField(required=False, allow_null=True)
    totalProperties = serializers.IntegerField(required=False)
    totalBookings = serializers.IntegerField(required=False)
    totalComplaints = serializers.IntegerField(required=False)
    activityScore = serializers.IntegerField(required=False)


class UserModerationPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['active', 'suspended', 'banned'],
        required=False,
    )
    verified = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if 'status' not in attrs and 'verified' not in attrs:
            raise serializers.ValidationError(
                'Provide status and/or verified.',
            )
        return attrs
