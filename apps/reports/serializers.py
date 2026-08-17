from rest_framework import serializers

from reports.models import ExpenseReport, Reminder, ReminderSettings, TaxDocument


def _dt_str(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat().replace('+00:00', 'Z')


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


class ExpenseCategorySerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    type = serializers.CharField()
    color = serializers.CharField()


class BudgetPatchSerializer(serializers.Serializer):
    monthlyLimit = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        source='monthly_limit',
    )
    alerts = serializers.JSONField(required=False)


class ExpenseReportSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    reportType = serializers.CharField(source='report_type')
    period = serializers.SerializerMethodField()
    generatedAt = serializers.SerializerMethodField()
    generatedBy = serializers.CharField(source='generated_by', allow_blank=True)
    fileUrl = serializers.CharField(source='file_url', allow_blank=True)
    fileName = serializers.CharField(source='file_name', allow_blank=True)

    class Meta:
        model = ExpenseReport
        fields = [
            'id',
            'userId',
            'reportType',
            'period',
            'generatedAt',
            'generatedBy',
            'data',
            'fileUrl',
            'fileName',
            'format',
        ]

    def get_period(self, obj) -> dict:
        return {
            'startDate': obj.period_start.isoformat(),
            'endDate': obj.period_end.isoformat(),
        }

    def get_generatedAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''


class ExpenseReportCreateSerializer(serializers.Serializer):
    startDate = serializers.DateField(source='period_start')
    endDate = serializers.DateField(source='period_end')
    format = serializers.ChoiceField(choices=['pdf', 'excel', 'csv'], default='pdf')
    reportType = serializers.ChoiceField(
        choices=['expense', 'payment', 'tax', 'comprehensive'],
        required=False,
        default='expense',
        source='report_type',
    )


class TaxDocumentSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    taxYear = serializers.IntegerField(source='tax_year')
    documentType = serializers.CharField(source='document_type')
    period = serializers.SerializerMethodField()
    generatedAt = serializers.SerializerMethodField()
    totalAmount = serializers.SerializerMethodField()
    fileUrl = serializers.CharField(source='file_url', allow_blank=True)
    fileName = serializers.CharField(source='file_name', allow_blank=True)
    verifiedAt = serializers.SerializerMethodField()
    verifiedBy = serializers.CharField(source='verified_by', allow_blank=True)

    class Meta:
        model = TaxDocument
        fields = [
            'id',
            'userId',
            'taxYear',
            'documentType',
            'period',
            'generatedAt',
            'totalAmount',
            'breakdown',
            'fileUrl',
            'fileName',
            'verified',
            'verifiedAt',
            'verifiedBy',
        ]

    def get_period(self, obj) -> dict:
        return {
            'startDate': obj.period_start.isoformat(),
            'endDate': obj.period_end.isoformat(),
        }

    def get_generatedAt(self, obj) -> str:
        return _dt_str(obj.created_at) or ''

    def get_totalAmount(self, obj) -> float:
        return _money(obj.total_amount)

    def get_verifiedAt(self, obj) -> str | None:
        return _dt_str(obj.verified_at)


class TaxDocumentCreateSerializer(serializers.Serializer):
    taxYear = serializers.IntegerField(source='tax_year')
    documentType = serializers.ChoiceField(
        choices=['rent_receipt', 'expense_summary', 'tax_certificate'],
        source='document_type',
    )
    startDate = serializers.DateField(source='period_start')
    endDate = serializers.DateField(source='period_end')


class ReminderSettingsSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    rentReminders = serializers.JSONField(source='rent_reminders')
    billReminders = serializers.JSONField(source='bill_reminders')
    maintenanceReminders = serializers.JSONField(source='maintenance_reminders')
    customReminders = serializers.JSONField(source='custom_reminders')

    class Meta:
        model = ReminderSettings
        fields = [
            'userId',
            'rentReminders',
            'billReminders',
            'maintenanceReminders',
            'customReminders',
        ]


class ReminderSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    scheduledDate = serializers.SerializerMethodField()
    sentDate = serializers.SerializerMethodField()
    relatedEntityId = serializers.CharField(source='related_entity_id', allow_blank=True)
    relatedEntityType = serializers.CharField(source='related_entity_type', allow_blank=True)

    class Meta:
        model = Reminder
        fields = [
            'id',
            'userId',
            'type',
            'title',
            'message',
            'scheduledDate',
            'sentDate',
            'channels',
            'status',
            'relatedEntityId',
            'relatedEntityType',
            'metadata',
        ]

    def get_scheduledDate(self, obj) -> str:
        return _dt_str(obj.scheduled_date) or ''

    def get_sentDate(self, obj) -> str | None:
        return _dt_str(obj.sent_date)


class ReminderCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=['rent_due', 'bill_due', 'maintenance', 'custom'])
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    scheduledDate = serializers.DateTimeField(source='scheduled_date')
    channels = serializers.JSONField(required=False, default=list)
    relatedEntityId = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        source='related_entity_id',
    )
    relatedEntityType = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        source='related_entity_type',
    )
    metadata = serializers.JSONField(required=False, default=dict)


class ReminderPatchSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['pending', 'sent', 'failed', 'cancelled'],
        required=False,
    )
