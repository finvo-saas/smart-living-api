from rest_framework import serializers

from core.services.media import media_storage
from documents.models import AgreementRenewal, Checklist, RentalAgreement


def _document_url(obj, request=None) -> str:
    """Signed URL for a privately stored document, else the external link."""
    if obj.document_key:
        return media_storage.signed_url(obj.document_key, request=request)
    return obj.document_url or ''


class DocumentKeyField(serializers.CharField):
    """Storage key returned by an upload, restricted to the documents folder."""

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('allow_blank', True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        return media_storage.ensure_key(super().to_internal_value(data), 'document')


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


def _date_str(dt) -> str:
    if dt is None:
        return ''
    return dt.isoformat()


class RentalAgreementSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    scopeType = serializers.CharField(source='scope_type', read_only=True)
    scopeId = serializers.UUIDField(source='scope_id', read_only=True, allow_null=True)
    propertyId = serializers.UUIDField(source='property_id')
    propertyName = serializers.CharField(source='property_name')
    flatId = serializers.SerializerMethodField()
    flatNumber = serializers.CharField(source='flat_number', allow_blank=True)
    agreementType = serializers.CharField(source='agreement_type')
    startDate = serializers.DateField(source='start_date')
    endDate = serializers.DateField(source='end_date')
    monthlyRent = serializers.DecimalField(
        source='monthly_rent',
        max_digits=12,
        decimal_places=2,
    )
    securityDeposit = serializers.DecimalField(
        source='security_deposit',
        max_digits=12,
        decimal_places=2,
    )
    documentKey = serializers.CharField(source='document_key', read_only=True)
    documentUrl = serializers.SerializerMethodField()
    documentName = serializers.CharField(source='document_name', allow_blank=True)
    documentSize = serializers.IntegerField(source='document_size')
    uploadedAt = serializers.SerializerMethodField()
    uploadedBy = serializers.CharField(source='uploaded_by', allow_blank=True)
    expiryDate = serializers.DateField(source='expiry_date')
    renewalReminderDays = serializers.JSONField(source='renewal_reminder_days')
    terms = serializers.JSONField(required=False)
    tenantSignature = serializers.CharField(source='tenant_signature', read_only=True)
    ownerSignature = serializers.CharField(source='owner_signature', read_only=True)
    tenantSignedAt = serializers.SerializerMethodField()
    ownerSignedAt = serializers.SerializerMethodField()
    tenantSignedName = serializers.CharField(source='tenant_signed_name', read_only=True)
    ownerSignedName = serializers.CharField(source='owner_signed_name', read_only=True)
    signatureStatus = serializers.SerializerMethodField()

    class Meta:
        model = RentalAgreement
        fields = [
            'id',
            'userId',
            'scopeType',
            'scopeId',
            'propertyId',
            'propertyName',
            'flatId',
            'flatNumber',
            'agreementType',
            'startDate',
            'endDate',
            'monthlyRent',
            'securityDeposit',
            'documentKey',
            'documentUrl',
            'documentName',
            'documentSize',
            'uploadedAt',
            'uploadedBy',
            'expiryDate',
            'renewalReminderDays',
            'status',
            'terms',
            'tenantSignature',
            'ownerSignature',
            'tenantSignedAt',
            'ownerSignedAt',
            'tenantSignedName',
            'ownerSignedName',
            'signatureStatus',
        ]

    def get_flatId(self, obj) -> str | None:
        return str(obj.flat_id) if obj.flat_id else None

    def get_documentUrl(self, obj) -> str:
        return _document_url(obj, self.context.get('request'))

    def get_uploadedAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_tenantSignedAt(self, obj):
        return _dt_str(obj.tenant_signed_at)

    def get_ownerSignedAt(self, obj):
        return _dt_str(obj.owner_signed_at)

    def get_signatureStatus(self, obj):
        tenant = bool(obj.tenant_signature)
        owner = bool(obj.owner_signature)
        if tenant and owner:
            return 'fully_signed'
        if tenant or owner:
            return 'partially_signed'
        return 'unsigned'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['monthlyRent'] = _money(instance.monthly_rent)
        data['securityDeposit'] = _money(instance.security_deposit)
        return data


class RentalAgreementWriteSerializer(serializers.Serializer):
    scopeType = serializers.ChoiceField(
        choices=['mess', 'building', 'hotel'],
        required=False,
        default='building',
        source='scope_type',
    )
    scopeId = serializers.UUIDField(required=False, allow_null=True, source='scope_id')
    propertyId = serializers.UUIDField(source='property_id')
    propertyName = serializers.CharField(source='property_name')
    flatId = serializers.UUIDField(required=False, allow_null=True, source='flat_id')
    flatNumber = serializers.CharField(required=False, allow_blank=True, source='flat_number')
    agreementType = serializers.ChoiceField(
        choices=['rental', 'lease', 'sublease'],
        source='agreement_type',
        default='rental',
    )
    startDate = serializers.DateField(source='start_date')
    endDate = serializers.DateField(source='end_date')
    monthlyRent = serializers.DecimalField(
        source='monthly_rent',
        max_digits=12,
        decimal_places=2,
    )
    securityDeposit = serializers.DecimalField(
        source='security_deposit',
        max_digits=12,
        decimal_places=2,
    )
    documentKey = DocumentKeyField(source='document_key')
    documentUrl = serializers.URLField(required=False, allow_blank=True, source='document_url')
    documentName = serializers.CharField(required=False, allow_blank=True, source='document_name')
    documentSize = serializers.IntegerField(required=False, default=0, source='document_size')
    uploadedBy = serializers.CharField(required=False, allow_blank=True, source='uploaded_by')
    expiryDate = serializers.DateField(source='expiry_date')
    renewalReminderDays = serializers.JSONField(
        required=False,
        default=list,
        source='renewal_reminder_days',
    )
    status = serializers.ChoiceField(
        choices=['active', 'expired', 'renewed', 'terminated'],
        required=False,
        default='active',
    )
    terms = serializers.JSONField(required=False, default=dict)

    def create_agreement(self, user):
        data = self.validated_data.copy()
        data['uploaded_by'] = data.get('uploaded_by') or str(user.id)
        if not data.get('scope_id'):
            data['scope_id'] = data['property_id']
        if not data.get('scope_type'):
            data['scope_type'] = 'building'
        return RentalAgreement.objects.create(user=user, **data)


class AgreementRenewalSerializer(serializers.ModelSerializer):
    agreementId = serializers.UUIDField(source='agreement_id', read_only=True)
    newStartDate = serializers.DateField(source='new_start_date')
    newEndDate = serializers.DateField(source='new_end_date')
    newMonthlyRent = serializers.DecimalField(
        source='new_monthly_rent',
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    documentKey = serializers.CharField(source='document_key', read_only=True)
    documentUrl = serializers.SerializerMethodField()
    renewedAt = serializers.SerializerMethodField()
    renewedBy = serializers.CharField(source='renewed_by', allow_blank=True)

    class Meta:
        model = AgreementRenewal
        fields = [
            'id',
            'agreementId',
            'newStartDate',
            'newEndDate',
            'newMonthlyRent',
            'documentKey',
            'documentUrl',
            'renewedAt',
            'renewedBy',
        ]

    def get_documentUrl(self, obj) -> str:
        return _document_url(obj, self.context.get('request'))

    def get_renewedAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.new_monthly_rent is not None:
            data['newMonthlyRent'] = _money(instance.new_monthly_rent)
        return data


class AgreementRenewalWriteSerializer(serializers.Serializer):
    newStartDate = serializers.DateField(source='new_start_date')
    newEndDate = serializers.DateField(source='new_end_date')
    newMonthlyRent = serializers.DecimalField(
        required=False,
        allow_null=True,
        source='new_monthly_rent',
        max_digits=12,
        decimal_places=2,
    )
    documentKey = DocumentKeyField(source='document_key')
    documentUrl = serializers.URLField(required=False, allow_blank=True, source='document_url')
    renewedBy = serializers.CharField(required=False, allow_blank=True, source='renewed_by')


class ChecklistSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    propertyId = serializers.UUIDField(source='property_id')
    propertyName = serializers.CharField(source='property_name')
    flatId = serializers.SerializerMethodField()
    flatNumber = serializers.CharField(source='flat_number', allow_blank=True)
    completedAt = serializers.SerializerMethodField()
    completedBy = serializers.CharField(source='completed_by', allow_blank=True)
    totalEstimatedValue = serializers.SerializerMethodField()
    totalRepairCost = serializers.SerializerMethodField()
    securityDepositAmount = serializers.SerializerMethodField()
    securityDepositReturned = serializers.SerializerMethodField()
    securityDepositReturnDate = serializers.SerializerMethodField()
    securityDepositDeductions = serializers.JSONField(source='security_deposit_deductions')
    approvedBy = serializers.CharField(source='approved_by', allow_blank=True)
    approvedAt = serializers.SerializerMethodField()

    class Meta:
        model = Checklist
        fields = [
            'id',
            'userId',
            'propertyId',
            'propertyName',
            'flatId',
            'flatNumber',
            'type',
            'completedAt',
            'completedBy',
            'items',
            'photos',
            'notes',
            'totalEstimatedValue',
            'totalRepairCost',
            'securityDepositAmount',
            'securityDepositReturned',
            'securityDepositReturnDate',
            'securityDepositDeductions',
            'status',
            'approvedBy',
            'approvedAt',
        ]

    def get_flatId(self, obj) -> str | None:
        return str(obj.flat_id) if obj.flat_id else None

    def get_completedAt(self, obj) -> str | None:
        return _dt_str(obj.completed_at)

    def get_approvedAt(self, obj) -> str | None:
        return _dt_str(obj.approved_at)

    def get_totalEstimatedValue(self, obj):
        return _money(obj.total_estimated_value) if obj.total_estimated_value else None

    def get_totalRepairCost(self, obj):
        return _money(obj.total_repair_cost) if obj.total_repair_cost else None

    def get_securityDepositAmount(self, obj) -> float:
        return _money(obj.security_deposit_amount)

    def get_securityDepositReturned(self, obj):
        return _money(obj.security_deposit_returned) if obj.security_deposit_returned else None

    def get_securityDepositReturnDate(self, obj) -> str | None:
        return _date_str(obj.security_deposit_return_date) if obj.security_deposit_return_date else None


class ChecklistWriteSerializer(serializers.Serializer):
    propertyId = serializers.UUIDField(source='property_id')
    propertyName = serializers.CharField(source='property_name')
    flatId = serializers.UUIDField(required=False, allow_null=True, source='flat_id')
    flatNumber = serializers.CharField(required=False, allow_blank=True, source='flat_number')
    type = serializers.ChoiceField(choices=['move_in', 'move_out'])
    completedAt = serializers.DateTimeField(required=False, allow_null=True, source='completed_at')
    completedBy = serializers.CharField(required=False, allow_blank=True, source='completed_by')
    items = serializers.JSONField(required=False, default=list)
    photos = serializers.JSONField(required=False, default=list)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    totalEstimatedValue = serializers.DecimalField(
        required=False,
        allow_null=True,
        source='total_estimated_value',
        max_digits=12,
        decimal_places=2,
    )
    totalRepairCost = serializers.DecimalField(
        required=False,
        allow_null=True,
        source='total_repair_cost',
        max_digits=12,
        decimal_places=2,
    )
    securityDepositAmount = serializers.DecimalField(
        source='security_deposit_amount',
        max_digits=12,
        decimal_places=2,
    )
    securityDepositReturned = serializers.DecimalField(
        required=False,
        allow_null=True,
        source='security_deposit_returned',
        max_digits=12,
        decimal_places=2,
    )
    securityDepositReturnDate = serializers.DateField(
        required=False,
        allow_null=True,
        source='security_deposit_return_date',
    )
    securityDepositDeductions = serializers.JSONField(
        required=False,
        default=list,
        source='security_deposit_deductions',
    )
    status = serializers.ChoiceField(
        choices=['draft', 'completed', 'approved', 'disputed'],
        required=False,
        default='draft',
    )
    approvedBy = serializers.CharField(required=False, allow_blank=True, source='approved_by')
    approvedAt = serializers.DateTimeField(required=False, allow_null=True, source='approved_at')

    def create_checklist(self, user):
        data = self.validated_data.copy()
        data['completed_by'] = data.get('completed_by') or str(user.id)
        return Checklist.objects.create(user=user, **data)
