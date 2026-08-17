from decimal import Decimal

from rest_framework import serializers

from billing.models import (
    Bill,
    BillGenerationRule,
    BillItem,
    BillStatus,
    BillTemplate,
    BillTemplateItem,
    MeterReading,
)


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _date_str(dt) -> str:
    if dt is None:
        return ''
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


def _dt_str(dt) -> str:
    if dt is None:
        return ''
    return dt.isoformat()


class BillItemSerializer(serializers.ModelSerializer):
    calculationType = serializers.CharField(
        source='calculation_type',
        required=False,
        allow_blank=True,
    )
    unitRate = serializers.FloatField(source='unit_rate', required=False, allow_null=True)
    previousReading = serializers.FloatField(
        source='previous_reading',
        required=False,
        allow_null=True,
    )
    currentReading = serializers.FloatField(
        source='current_reading',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = BillItem
        fields = (
            'id',
            'description',
            'amount',
            'type',
            'calculationType',
            'unitRate',
            'previousReading',
            'currentReading',
            'consumption',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['amount'] = _money(instance.amount)
        if data.get('unitRate') is not None:
            data['unitRate'] = float(instance.unit_rate)
        return data


class BillItemWriteSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    type = serializers.CharField()
    calculationType = serializers.CharField(required=False, allow_blank=True)
    unitRate = serializers.FloatField(required=False, allow_null=True)
    previousReading = serializers.FloatField(required=False, allow_null=True)
    currentReading = serializers.FloatField(required=False, allow_null=True)
    consumption = serializers.FloatField(required=False, allow_null=True)


class MeterReadingSerializer(serializers.ModelSerializer):
    propertyId = serializers.UUIDField(source='property_id')
    propertyType = serializers.CharField(source='property_type')
    flatId = serializers.SerializerMethodField()
    seatId = serializers.CharField(source='seat_id', required=False, allow_blank=True)
    previousElectricity = serializers.FloatField(
        source='previous_electricity',
        required=False,
        allow_null=True,
    )
    previousGas = serializers.FloatField(source='previous_gas', required=False, allow_null=True)
    previousWater = serializers.FloatField(source='previous_water', required=False, allow_null=True)
    electricityConsumption = serializers.FloatField(
        source='electricity_consumption',
        required=False,
        allow_null=True,
    )
    gasConsumption = serializers.FloatField(
        source='gas_consumption',
        required=False,
        allow_null=True,
    )
    waterConsumption = serializers.FloatField(
        source='water_consumption',
        required=False,
        allow_null=True,
    )
    submittedAt = serializers.DateTimeField(source='submitted_at', read_only=True)
    submittedBy = serializers.SerializerMethodField()

    class Meta:
        model = MeterReading
        fields = (
            'id',
            'propertyId',
            'propertyType',
            'flatId',
            'seatId',
            'month',
            'year',
            'electricity',
            'gas',
            'water',
            'previousElectricity',
            'previousGas',
            'previousWater',
            'electricityConsumption',
            'gasConsumption',
            'waterConsumption',
            'submittedAt',
            'submittedBy',
        )

    def get_flatId(self, obj):
        return str(obj.flat_id) if obj.flat_id else None

    def get_submittedBy(self, obj):
        if obj.submitted_by_id:
            return str(obj.submitted_by_id)
        return ''


class BillSerializer(serializers.ModelSerializer):
    tenantName = serializers.CharField(source='tenant_name')
    tenantId = serializers.SerializerMethodField()
    propertyType = serializers.CharField(source='property_type')
    propertyName = serializers.CharField(source='property_name')
    propertyId = serializers.UUIDField(source='property_id')
    flatNumber = serializers.CharField(source='flat_number', allow_blank=True)
    seatNumber = serializers.CharField(source='seat_number', allow_blank=True)
    dueDate = serializers.DateField(source='due_date', format='%Y-%m-%d')
    paidDate = serializers.SerializerMethodField()
    items = BillItemSerializer(many=True, read_only=True)
    createdAt = serializers.SerializerMethodField()
    templateId = serializers.SerializerMethodField()
    meterReadings = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = (
            'id',
            'tenantName',
            'tenantId',
            'propertyType',
            'propertyName',
            'propertyId',
            'flatNumber',
            'seatNumber',
            'month',
            'year',
            'amount',
            'dueDate',
            'paidDate',
            'status',
            'items',
            'createdAt',
            'templateId',
            'meterReadings',
        )

    def get_tenantId(self, obj):
        if obj.tenant_id_snapshot:
            return obj.tenant_id_snapshot
        if obj.tenant_id:
            return str(obj.tenant_id)
        return ''

    def get_paidDate(self, obj):
        return _date_str(obj.paid_date) if obj.paid_date else None

    def get_createdAt(self, obj):
        return _date_str(obj.created_at.date() if obj.created_at else None)

    def get_templateId(self, obj):
        return str(obj.template_id) if obj.template_id else None

    def get_meterReadings(self, obj):
        if obj.meter_reading_id:
            return MeterReadingSerializer(obj.meter_reading).data
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['amount'] = _money(instance.amount)
        return data


class BillBulkItemSerializer(BillSerializer):
    items = BillItemWriteSerializer(many=True, required=False)


class GenerateBillSerializer(serializers.Serializer):
    propertyId = serializers.UUIDField()
    propertyType = serializers.ChoiceField(choices=['apartment', 'mess'])
    month = serializers.CharField()
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    tenantId = serializers.CharField()
    flatId = serializers.UUIDField(required=False, allow_null=True)
    templateId = serializers.UUIDField(required=False, allow_null=True)
    items = BillItemWriteSerializer(many=True)


class BulkGenerateBillSerializer(serializers.Serializer):
    buildingId = serializers.UUIDField()
    flatIds = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    month = serializers.CharField()
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    templateId = serializers.UUIDField(required=False, allow_null=True)
    includeUnpaid = serializers.BooleanField(required=False, default=False)


class MarkPaidSerializer(serializers.Serializer):
    paidAt = serializers.DateField(required=False)


class BillTemplateItemSerializer(serializers.ModelSerializer):
    calculationType = serializers.CharField(source='calculation_type')
    fixedAmount = serializers.FloatField(source='fixed_amount', required=False, allow_null=True)
    unitRate = serializers.FloatField(source='unit_rate', required=False, allow_null=True)
    baseItemId = serializers.CharField(source='base_item_id', required=False, allow_blank=True)
    meterType = serializers.CharField(source='meter_type', required=False, allow_blank=True)
    serviceCharge = serializers.FloatField(source='service_charge', required=False, allow_null=True)

    class Meta:
        model = BillTemplateItem
        fields = (
            'id',
            'description',
            'type',
            'calculationType',
            'fixedAmount',
            'unitRate',
            'percentage',
            'baseItemId',
            'meterType',
            'serviceCharge',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.fixed_amount is not None:
            data['fixedAmount'] = _money(instance.fixed_amount)
        if instance.unit_rate is not None:
            data['unitRate'] = float(instance.unit_rate)
        if instance.service_charge is not None:
            data['serviceCharge'] = _money(instance.service_charge)
        return data


class BillTemplateItemWriteSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    description = serializers.CharField()
    type = serializers.CharField()
    calculationType = serializers.CharField()
    fixedAmount = serializers.FloatField(required=False, allow_null=True)
    unitRate = serializers.FloatField(required=False, allow_null=True)
    percentage = serializers.FloatField(required=False, allow_null=True)
    baseItemId = serializers.CharField(required=False, allow_blank=True)
    meterType = serializers.CharField(required=False, allow_blank=True)
    serviceCharge = serializers.FloatField(required=False, allow_null=True)


class BillTemplateSerializer(serializers.ModelSerializer):
    propertyId = serializers.UUIDField(source='property_id')
    propertyType = serializers.CharField(source='property_type')
    flatId = serializers.UUIDField(source='flat_id', required=False, allow_null=True)
    seatId = serializers.CharField(source='seat_id', required=False, allow_blank=True)
    isActive = serializers.BooleanField(source='is_active')
    items = BillTemplateItemSerializer(many=True, read_only=True)
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    class Meta:
        model = BillTemplate
        fields = (
            'id',
            'name',
            'description',
            'propertyId',
            'propertyType',
            'flatId',
            'seatId',
            'items',
            'isActive',
            'createdAt',
            'updatedAt',
        )

    def get_createdAt(self, obj):
        return _date_str(obj.created_at.date() if obj.created_at else None)

    def get_updatedAt(self, obj):
        return _date_str(obj.updated_at.date() if obj.updated_at else None)


class BillTemplateBulkSerializer(BillTemplateSerializer):
    items = BillTemplateItemWriteSerializer(many=True, required=False)


class BillGenerationRuleSerializer(serializers.ModelSerializer):
    propertyId = serializers.UUIDField(source='property_id', required=False, allow_null=True)
    propertyType = serializers.CharField(
        source='property_type',
        required=False,
        allow_blank=True,
    )
    templateId = serializers.UUIDField(source='template_id')
    isActive = serializers.BooleanField(source='is_active')
    lastRun = serializers.SerializerMethodField()
    nextRun = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    class Meta:
        model = BillGenerationRule
        fields = (
            'id',
            'name',
            'description',
            'propertyId',
            'propertyType',
            'templateId',
            'schedule',
            'isActive',
            'lastRun',
            'nextRun',
            'createdAt',
            'updatedAt',
        )

    def get_lastRun(self, obj):
        return _date_str(obj.last_run) if obj.last_run else None

    def get_nextRun(self, obj):
        return _date_str(obj.next_run) if obj.next_run else None

    def get_createdAt(self, obj):
        return _date_str(obj.created_at.date() if obj.created_at else None)

    def get_updatedAt(self, obj):
        return _date_str(obj.updated_at.date() if obj.updated_at else None)


class BillRuleBulkSerializer(BillGenerationRuleSerializer):
    templateId = serializers.UUIDField(required=False, allow_null=True)


class MeterReadingBulkSerializer(MeterReadingSerializer):
    propertyId = serializers.UUIDField(source='property_id')
    flatId = serializers.UUIDField(required=False, allow_null=True)

    class Meta(MeterReadingSerializer.Meta):
        fields = MeterReadingSerializer.Meta.fields
