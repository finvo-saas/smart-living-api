from rest_framework import serializers

from payments.models import (
    OwnerPayout,
    PaymentSchedule,
    PaymentTransaction,
    ScheduledPayment,
)


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


class PaymentTransactionSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id')
    billId = serializers.SerializerMethodField()
    billName = serializers.CharField(source='bill_name')
    propertyName = serializers.CharField(source='property_name', allow_blank=True)
    tenantName = serializers.CharField(source='tenant_name', allow_blank=True)
    paymentMethod = serializers.CharField(source='payment_method')
    accountNumber = serializers.CharField(source='account_number', allow_blank=True)
    transactionId = serializers.CharField(source='transaction_id')
    failureReason = serializers.CharField(source='failure_reason', allow_blank=True)
    receiptNote = serializers.CharField(source='receipt_note', allow_blank=True)
    receiptFileName = serializers.CharField(source='receipt_file_name', allow_blank=True)
    createdAt = serializers.SerializerMethodField()
    completedAt = serializers.SerializerMethodField()

    class Meta:
        model = PaymentTransaction
        fields = [
            'id',
            'userId',
            'billId',
            'billName',
            'propertyName',
            'tenantName',
            'amount',
            'paymentMethod',
            'accountNumber',
            'transactionId',
            'status',
            'failureReason',
            'receiptNote',
            'receiptFileName',
            'createdAt',
            'completedAt',
        ]

    def get_billId(self, obj) -> str:
        return str(obj.bill_id) if obj.bill_id else ''

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_completedAt(self, obj) -> str | None:
        return _dt_str(obj.completed_at)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['amount'] = _money(instance.amount)
        return data


class PayBillSerializer(serializers.Serializer):
    billId = serializers.UUIDField()
    billName = serializers.CharField(required=False, allow_blank=True)
    propertyName = serializers.CharField(required=False, allow_blank=True)
    tenantName = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    paymentMethod = serializers.CharField()
    accountNumber = serializers.CharField(required=False, allow_blank=True, default='')
    idempotencyKey = serializers.CharField(required=False, allow_blank=True, default='')


class RecordCashSerializer(serializers.Serializer):
    billId = serializers.UUIDField()
    billName = serializers.CharField(required=False, allow_blank=True)
    propertyName = serializers.CharField(required=False, allow_blank=True)
    tenantName = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    receivedDate = serializers.CharField()
    receivedBy = serializers.CharField(required=False, allow_blank=True, default='')
    receiptNote = serializers.CharField(required=False, allow_blank=True, default='')
    receiptFileName = serializers.CharField(required=False, allow_blank=True, default='')
    paymentMethod = serializers.CharField(required=False, allow_blank=True, default='Cash')
    transactionId = serializers.CharField(required=False, allow_blank=True, default='')


class CollectionSettingsSerializer(serializers.Serializer):
    collectionMode = serializers.CharField(required=False)
    platformCollectEnabled = serializers.BooleanField(required=False)
    instructions = serializers.DictField(required=False)
    bkashNumber = serializers.CharField(required=False, allow_blank=True)
    nagadNumber = serializers.CharField(required=False, allow_blank=True)
    rocketNumber = serializers.CharField(required=False, allow_blank=True)
    bankName = serializers.CharField(required=False, allow_blank=True)
    bankAccountNumber = serializers.CharField(required=False, allow_blank=True)
    bankAccountName = serializers.CharField(required=False, allow_blank=True)
    paymentNote = serializers.CharField(required=False, allow_blank=True)


class GatewayCredentialSerializer(serializers.Serializer):
    gateway = serializers.CharField()
    displayName = serializers.CharField(required=False, allow_blank=True, default='')
    merchantNumber = serializers.CharField(required=False, allow_blank=True, default='')
    credentials = serializers.DictField(required=False)
    isActive = serializers.BooleanField(required=False, default=True)
    isSandbox = serializers.BooleanField(required=False, default=True)


class PaymentClaimCreateSerializer(serializers.Serializer):
    billId = serializers.UUIDField(required=False)
    messId = serializers.UUIDField(required=False)
    studentId = serializers.UUIDField(required=False)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    paymentMethod = serializers.CharField()
    transactionId = serializers.CharField(required=False, allow_blank=True, default='')
    note = serializers.CharField(required=False, allow_blank=True, default='')
    date = serializers.CharField(required=False, allow_blank=True, default='')


class PaymentClaimReviewSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class OwnerPayoutSerializer(serializers.ModelSerializer):
    ownerId = serializers.UUIDField(source='owner_id')
    billId = serializers.SerializerMethodField()
    billName = serializers.CharField(source='bill_name')
    tenantName = serializers.CharField(source='tenant_name')
    propertyName = serializers.CharField(source='property_name')
    grossAmount = serializers.SerializerMethodField()
    commissionRate = serializers.SerializerMethodField()
    commissionAmount = serializers.SerializerMethodField()
    netAmount = serializers.SerializerMethodField()
    paymentMethod = serializers.CharField(source='payment_method')
    transactionId = serializers.CharField(source='transaction_id')
    paidAt = serializers.SerializerMethodField()
    payoutDate = serializers.SerializerMethodField()

    class Meta:
        model = OwnerPayout
        fields = [
            'id',
            'ownerId',
            'billId',
            'billName',
            'tenantName',
            'propertyName',
            'grossAmount',
            'commissionRate',
            'commissionAmount',
            'netAmount',
            'paymentMethod',
            'transactionId',
            'status',
            'paidAt',
            'payoutDate',
        ]

    def get_billId(self, obj) -> str:
        return str(obj.bill_id) if obj.bill_id else ''

    def get_grossAmount(self, obj) -> float:
        return _money(obj.gross_amount)

    def get_commissionRate(self, obj) -> float:
        return _money(obj.commission_rate)

    def get_commissionAmount(self, obj) -> float:
        return _money(obj.commission_amount)

    def get_netAmount(self, obj) -> float:
        return _money(obj.net_amount)

    def get_paidAt(self, obj) -> str:
        return _dt_str(obj.paid_at) or ''

    def get_payoutDate(self, obj) -> str | None:
        if obj.payout_date is None:
            return None
        return obj.payout_date.isoformat()


class ScheduledPaymentSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id')
    billId = serializers.SerializerMethodField()
    billName = serializers.CharField(source='bill_name')
    scheduledDate = serializers.DateField(source='scheduled_date', format='%Y-%m-%d')
    scheduledTime = serializers.CharField(source='scheduled_time', allow_blank=True)
    paymentMethod = serializers.CharField(source='payment_method')
    accountNumber = serializers.CharField(source='account_number', allow_blank=True)
    transactionId = serializers.CharField(source='transaction_id', allow_blank=True)
    reminderEnabled = serializers.BooleanField(source='reminder_enabled')
    reminderDays = serializers.JSONField(source='reminder_days')
    autoRetry = serializers.BooleanField(source='auto_retry')
    maxRetries = serializers.IntegerField(source='max_retries')
    retryCount = serializers.IntegerField(source='retry_count')
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()
    completedAt = serializers.SerializerMethodField()
    failureReason = serializers.CharField(source='failure_reason', allow_blank=True)

    class Meta:
        model = ScheduledPayment
        fields = [
            'id',
            'userId',
            'billId',
            'billName',
            'amount',
            'scheduledDate',
            'scheduledTime',
            'paymentMethod',
            'accountNumber',
            'transactionId',
            'status',
            'reminderEnabled',
            'reminderDays',
            'autoRetry',
            'maxRetries',
            'retryCount',
            'createdAt',
            'updatedAt',
            'completedAt',
            'failureReason',
            'metadata',
        ]

    def get_billId(self, obj) -> str:
        return str(obj.bill_id) if obj.bill_id else ''

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_updatedAt(self, obj) -> str:
        return _dt_str(obj.updated_at) or ''

    def get_completedAt(self, obj) -> str | None:
        return _dt_str(obj.completed_at)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['amount'] = _money(instance.amount)
        return data


class ScheduledPaymentWriteSerializer(serializers.Serializer):
    billId = serializers.UUIDField(required=False, allow_null=True)
    billName = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    scheduledDate = serializers.DateField()
    scheduledTime = serializers.CharField(required=False, allow_blank=True, default='')
    paymentMethod = serializers.CharField()
    accountNumber = serializers.CharField(required=False, allow_blank=True, default='')
    reminderEnabled = serializers.BooleanField(required=False, default=True)
    reminderDays = serializers.JSONField(required=False, default=list)
    autoRetry = serializers.BooleanField(required=False, default=False)
    maxRetries = serializers.IntegerField(required=False, default=0)
    metadata = serializers.JSONField(required=False, default=dict)


class ScheduledPaymentPatchSerializer(serializers.Serializer):
    billName = serializers.CharField(required=False)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    scheduledDate = serializers.DateField(required=False)
    scheduledTime = serializers.CharField(required=False, allow_blank=True)
    paymentMethod = serializers.CharField(required=False)
    accountNumber = serializers.CharField(required=False, allow_blank=True)
    reminderEnabled = serializers.BooleanField(required=False)
    reminderDays = serializers.JSONField(required=False)
    autoRetry = serializers.BooleanField(required=False)
    maxRetries = serializers.IntegerField(required=False)
    metadata = serializers.JSONField(required=False)


class PaymentScheduleSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id')
    billId = serializers.SerializerMethodField()
    startDate = serializers.DateField(source='start_date', format='%Y-%m-%d')
    endDate = serializers.SerializerMethodField()
    paymentMethod = serializers.CharField(source='payment_method')
    reminderEnabled = serializers.BooleanField(source='reminder_enabled')
    reminderDays = serializers.JSONField(source='reminder_days')
    isActive = serializers.BooleanField(source='is_active')
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    class Meta:
        model = PaymentSchedule
        fields = [
            'id',
            'userId',
            'name',
            'description',
            'billId',
            'recurring',
            'frequency',
            'startDate',
            'endDate',
            'amount',
            'paymentMethod',
            'reminderEnabled',
            'reminderDays',
            'isActive',
            'createdAt',
            'updatedAt',
        ]

    def get_billId(self, obj) -> str:
        return str(obj.bill_id) if obj.bill_id else ''

    def get_endDate(self, obj) -> str | None:
        if obj.end_date is None:
            return None
        return obj.end_date.isoformat()

    def get_createdAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_updatedAt(self, obj) -> str:
        return _dt_str(obj.updated_at) or ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['amount'] = _money(instance.amount)
        if not data.get('frequency'):
            data['frequency'] = None
        return data


class SandboxCompleteSerializer(serializers.Serializer):
    transactionId = serializers.CharField()
