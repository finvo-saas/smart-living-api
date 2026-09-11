from django.contrib import admin

from billing.models import (
    Bill,
    BillGenerationRule,
    BillItem,
    BillTemplate,
    BillTemplateItem,
    MeterReading,
)
from core.admin import TimestampedModelAdmin


class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Bill)
class BillAdmin(TimestampedModelAdmin):
    list_display = (
        'tenant_name',
        'property_name',
        'month',
        'year',
        'amount',
        'status',
        'owner',
    )
    list_filter = ('status', 'property_type', 'year')
    search_fields = ('tenant_name', 'property_name', 'owner__phone')
    inlines = [BillItemInline]


class BillTemplateItemInline(admin.TabularInline):
    model = BillTemplateItem
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BillTemplate)
class BillTemplateAdmin(TimestampedModelAdmin):
    list_display = ('name', 'property_id', 'property_type', 'is_active', 'owner')
    list_filter = ('property_type', 'is_active')
    search_fields = ('name', 'owner__phone')
    inlines = [BillTemplateItemInline]


@admin.register(BillGenerationRule)
class BillGenerationRuleAdmin(TimestampedModelAdmin):
    list_display = ('name', 'template', 'is_active', 'owner', 'next_run')
    list_filter = ('is_active',)
    search_fields = ('name', 'owner__phone')


@admin.register(MeterReading)
class MeterReadingAdmin(TimestampedModelAdmin):
    list_display = (
        'property_id',
        'flat',
        'month',
        'year',
        'electricity',
        'gas',
        'water',
        'owner',
    )
    list_filter = ('year', 'property_type')
    search_fields = ('owner__phone',)
