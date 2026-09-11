from django.contrib import admin

from core.admin import TimestampedModelAdmin
from reports.models import (
    Budget,
    ExpenseCategory,
    ExpenseReport,
    Reminder,
    ReminderSettings,
    TaxDocument,
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(TimestampedModelAdmin):
    list_display = ('name', 'code', 'type')
    list_filter = ('type',)
    search_fields = ('name', 'code')


@admin.register(Budget)
class BudgetAdmin(TimestampedModelAdmin):
    list_display = ('user', 'category', 'period_month', 'period_year', 'monthly_limit')
    search_fields = ('user__phone',)


@admin.register(ExpenseReport)
class ExpenseReportAdmin(TimestampedModelAdmin):
    list_display = ('user', 'report_type', 'period_start', 'period_end', 'format')
    list_filter = ('report_type', 'format')
    search_fields = ('user__phone', 'file_name')


@admin.register(TaxDocument)
class TaxDocumentAdmin(TimestampedModelAdmin):
    list_display = ('user', 'tax_year', 'document_type', 'total_amount', 'verified')
    list_filter = ('document_type', 'verified')
    search_fields = ('user__phone', 'file_name')


@admin.register(Reminder)
class ReminderAdmin(TimestampedModelAdmin):
    list_display = ('user', 'title', 'status', 'scheduled_date')
    list_filter = ('status', 'type')
    search_fields = ('title', 'user__phone')


@admin.register(ReminderSettings)
class ReminderSettingsAdmin(TimestampedModelAdmin):
    list_display = ('user',)
    search_fields = ('user__phone',)
