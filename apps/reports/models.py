from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


class ExpenseCategoryType(models.TextChoices):
    RENT = 'rent', 'Rent'
    UTILITIES = 'utilities', 'Utilities'
    MAINTENANCE = 'maintenance', 'Maintenance'
    SERVICE = 'service', 'Service'
    OTHER = 'other', 'Other'


class ExpenseCategory(UUIDModel, TimestampedModel):
    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ExpenseCategoryType.choices)
    color = models.CharField(max_length=20)

    class Meta:
        db_table = 'reports_expense_category'
        ordering = ('code',)

    def __str__(self):
        return self.name


class Budget(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='budgets',
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE,
        related_name='budgets',
    )
    monthly_limit = models.DecimalField(max_digits=12, decimal_places=2)
    current_spending = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    period_month = models.CharField(max_length=20)
    period_year = models.PositiveIntegerField()
    alerts = models.JSONField(default=dict)

    class Meta:
        db_table = 'reports_budget'
        unique_together = [('user', 'category', 'period_month', 'period_year')]
        ordering = ('category__code',)


class ReportFormat(models.TextChoices):
    PDF = 'pdf', 'PDF'
    EXCEL = 'excel', 'Excel'
    CSV = 'csv', 'CSV'


class ReportType(models.TextChoices):
    EXPENSE = 'expense', 'Expense'
    PAYMENT = 'payment', 'Payment'
    TAX = 'tax', 'Tax'
    COMPREHENSIVE = 'comprehensive', 'Comprehensive'


class ExpenseReport(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='expense_reports',
    )
    report_type = models.CharField(
        max_length=20,
        choices=ReportType.choices,
        default=ReportType.EXPENSE,
    )
    period_start = models.DateField()
    period_end = models.DateField()
    generated_by = models.CharField(max_length=255, blank=True, default='')
    data = models.JSONField(default=dict)
    file_url = models.URLField(blank=True, default='')
    file_name = models.CharField(max_length=255, blank=True, default='')
    format = models.CharField(
        max_length=10,
        choices=ReportFormat.choices,
        default=ReportFormat.PDF,
    )

    class Meta:
        db_table = 'reports_expense_report'
        ordering = ('-created_at',)


class TaxDocumentType(models.TextChoices):
    RENT_RECEIPT = 'rent_receipt', 'Rent Receipt'
    EXPENSE_SUMMARY = 'expense_summary', 'Expense Summary'
    TAX_CERTIFICATE = 'tax_certificate', 'Tax Certificate'


class TaxDocument(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tax_documents',
    )
    tax_year = models.PositiveIntegerField()
    document_type = models.CharField(max_length=30, choices=TaxDocumentType.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    breakdown = models.JSONField(default=list)
    file_url = models.URLField(blank=True, default='')
    file_name = models.CharField(max_length=255, blank=True, default='')
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'reports_tax_document'
        ordering = ('-created_at',)


class ReminderType(models.TextChoices):
    RENT_DUE = 'rent_due', 'Rent Due'
    BILL_DUE = 'bill_due', 'Bill Due'
    MAINTENANCE = 'maintenance', 'Maintenance'
    CUSTOM = 'custom', 'Custom'


class ReminderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class Reminder(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reminders',
    )
    type = models.CharField(max_length=20, choices=ReminderType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    scheduled_date = models.DateTimeField()
    sent_date = models.DateTimeField(null=True, blank=True)
    channels = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=ReminderStatus.choices,
        default=ReminderStatus.PENDING,
    )
    related_entity_id = models.CharField(max_length=64, blank=True, default='')
    related_entity_type = models.CharField(max_length=64, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'reports_reminder'
        ordering = ('-scheduled_date',)


class ReminderSettings(UUIDModel, TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reminder_settings',
    )
    rent_reminders = models.JSONField(default=dict)
    bill_reminders = models.JSONField(default=dict)
    maintenance_reminders = models.JSONField(default=dict)
    custom_reminders = models.JSONField(default=dict)

    class Meta:
        db_table = 'reports_reminder_settings'
