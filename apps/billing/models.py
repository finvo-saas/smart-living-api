from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel
from portfolio.models import Flat


class BillStatus(models.TextChoices):
    PAID = 'paid', 'Paid'
    UNPAID = 'unpaid', 'Unpaid'
    OVERDUE = 'overdue', 'Overdue'


class PropertyKind(models.TextChoices):
    APARTMENT = 'apartment', 'Apartment'
    MESS = 'mess', 'Mess'


class BillItemType(models.TextChoices):
    RENT = 'rent', 'Rent'
    UTILITY = 'utility', 'Utility'
    MAINTENANCE = 'maintenance', 'Maintenance'
    OTHER = 'other', 'Other'


class CalculationType(models.TextChoices):
    FIXED = 'fixed', 'Fixed'
    METER = 'meter-based', 'Meter-based'
    PERCENTAGE = 'percentage', 'Percentage'


class MeterType(models.TextChoices):
    ELECTRICITY = 'electricity', 'Electricity'
    GAS = 'gas', 'Gas'
    WATER = 'water', 'Water'


class Bill(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owned_bills',
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tenant_bills',
        null=True,
        blank=True,
    )
    tenant_name = models.CharField(max_length=255)
    tenant_id_snapshot = models.CharField(max_length=64, blank=True, default='')
    property_type = models.CharField(max_length=20, choices=PropertyKind.choices)
    property_name = models.CharField(max_length=255)
    property_id = models.UUIDField(db_index=True)
    flat = models.ForeignKey(
        Flat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bills',
    )
    flat_number = models.CharField(max_length=40, blank=True, default='')
    seat_number = models.CharField(max_length=40, blank=True, default='')
    month = models.CharField(max_length=20)
    year = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=BillStatus.choices,
        default=BillStatus.UNPAID,
    )
    template = models.ForeignKey(
        'BillTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_bills',
    )
    meter_reading = models.ForeignKey(
        'MeterReading',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bills',
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'billing_bill'
        ordering = ('-year', '-created_at')
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['property_id', 'month', 'year']),
        ]

    def __str__(self):
        return f'{self.tenant_name} {self.month} {self.year}'


class BillItem(UUIDModel, TimestampedModel):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=20, choices=BillItemType.choices)
    calculation_type = models.CharField(
        max_length=20,
        choices=CalculationType.choices,
        blank=True,
        default='',
    )
    unit_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    previous_reading = models.FloatField(null=True, blank=True)
    current_reading = models.FloatField(null=True, blank=True)
    consumption = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'billing_bill_item'


class BillTemplate(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bill_templates',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    property_id = models.UUIDField(db_index=True)
    property_type = models.CharField(max_length=20, choices=PropertyKind.choices)
    flat_id = models.UUIDField(null=True, blank=True)
    seat_id = models.CharField(max_length=64, blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'billing_bill_template'
        ordering = ('-updated_at',)


class BillTemplateItem(UUIDModel, TimestampedModel):
    template = models.ForeignKey(
        BillTemplate,
        on_delete=models.CASCADE,
        related_name='items',
    )
    description = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=BillItemType.choices)
    calculation_type = models.CharField(
        max_length=20,
        choices=CalculationType.choices,
        default=CalculationType.FIXED,
    )
    fixed_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    unit_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    percentage = models.FloatField(null=True, blank=True)
    base_item_id = models.CharField(max_length=64, blank=True, default='')
    meter_type = models.CharField(
        max_length=20,
        choices=MeterType.choices,
        blank=True,
        default='',
    )
    service_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'billing_bill_template_item'


class MeterReading(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meter_readings',
    )
    property_id = models.UUIDField(db_index=True)
    property_type = models.CharField(max_length=20, choices=PropertyKind.choices)
    flat = models.ForeignKey(
        Flat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meter_readings',
    )
    seat_id = models.CharField(max_length=64, blank=True, default='')
    month = models.CharField(max_length=20)
    year = models.PositiveIntegerField()
    electricity = models.FloatField(null=True, blank=True)
    gas = models.FloatField(null=True, blank=True)
    water = models.FloatField(null=True, blank=True)
    previous_electricity = models.FloatField(null=True, blank=True)
    previous_gas = models.FloatField(null=True, blank=True)
    previous_water = models.FloatField(null=True, blank=True)
    electricity_consumption = models.FloatField(null=True, blank=True)
    gas_consumption = models.FloatField(null=True, blank=True)
    water_consumption = models.FloatField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='submitted_meter_readings',
    )

    class Meta:
        db_table = 'billing_meter_reading'
        ordering = ('-year', '-submitted_at')
        indexes = [
            models.Index(fields=['property_id', 'month', 'year']),
        ]


class BillGenerationRule(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bill_rules',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    property_id = models.UUIDField(null=True, blank=True)
    property_type = models.CharField(
        max_length=20,
        choices=PropertyKind.choices,
        blank=True,
        default='',
    )
    template = models.ForeignKey(
        BillTemplate,
        on_delete=models.CASCADE,
        related_name='rules',
    )
    schedule = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    last_run = models.DateField(null=True, blank=True)
    next_run = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'billing_generation_rule'
        ordering = ('-updated_at',)
