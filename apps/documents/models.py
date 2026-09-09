from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


class AgreementType(models.TextChoices):
    RENTAL = 'rental', 'Rental'
    LEASE = 'lease', 'Lease'
    SUBLEASE = 'sublease', 'Sublease'


class AgreementStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    EXPIRED = 'expired', 'Expired'
    RENEWED = 'renewed', 'Renewed'
    TERMINATED = 'terminated', 'Terminated'


class RentalAgreement(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rental_agreements',
    )
    property_id = models.UUIDField(db_index=True)
    property_name = models.CharField(max_length=255)
    flat_id = models.UUIDField(null=True, blank=True)
    flat_number = models.CharField(max_length=40, blank=True, default='')
    agreement_type = models.CharField(
        max_length=20,
        choices=AgreementType.choices,
        default=AgreementType.RENTAL,
    )
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=12, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=12, decimal_places=2)
    # Private uploads keep their storage key; the URL is signed per read.
    # document_url stays for externally hosted / pasted links.
    document_key = models.CharField(max_length=512, blank=True, default='')
    document_url = models.URLField(blank=True, default='')
    document_name = models.CharField(max_length=255, blank=True, default='')
    document_size = models.PositiveIntegerField(default=0)
    uploaded_by = models.CharField(max_length=255, blank=True, default='')
    expiry_date = models.DateField()
    renewal_reminder_days = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=AgreementStatus.choices,
        default=AgreementStatus.ACTIVE,
    )
    terms = models.JSONField(default=dict, blank=True)
    is_deleted = models.BooleanField(default=False)
    tenant_signature = models.TextField(blank=True, default='')
    owner_signature = models.TextField(blank=True, default='')
    tenant_signed_at = models.DateTimeField(null=True, blank=True)
    owner_signed_at = models.DateTimeField(null=True, blank=True)
    tenant_signed_name = models.CharField(max_length=255, blank=True, default='')
    owner_signed_name = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'documents_rental_agreement'
        ordering = ('-created_at',)


class AgreementRenewal(UUIDModel, TimestampedModel):
    agreement = models.ForeignKey(
        RentalAgreement,
        on_delete=models.CASCADE,
        related_name='renewals',
    )
    new_start_date = models.DateField()
    new_end_date = models.DateField()
    new_monthly_rent = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    document_key = models.CharField(max_length=512, blank=True, default='')
    document_url = models.URLField(blank=True, default='')
    renewed_by = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'documents_agreement_renewal'
        ordering = ('-created_at',)


class ChecklistType(models.TextChoices):
    MOVE_IN = 'move_in', 'Move In'
    MOVE_OUT = 'move_out', 'Move Out'


class ChecklistStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    COMPLETED = 'completed', 'Completed'
    APPROVED = 'approved', 'Approved'
    DISPUTED = 'disputed', 'Disputed'


class Checklist(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='checklists',
    )
    property_id = models.UUIDField(db_index=True)
    property_name = models.CharField(max_length=255)
    flat_id = models.UUIDField(null=True, blank=True)
    flat_number = models.CharField(max_length=40, blank=True, default='')
    type = models.CharField(max_length=20, choices=ChecklistType.choices)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.CharField(max_length=255, blank=True, default='')
    items = models.JSONField(default=list)
    photos = models.JSONField(default=list)
    notes = models.TextField(blank=True, default='')
    total_estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    total_repair_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    security_deposit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    security_deposit_returned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    security_deposit_return_date = models.DateField(null=True, blank=True)
    security_deposit_deductions = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ChecklistStatus.choices,
        default=ChecklistStatus.DRAFT,
    )
    approved_by = models.CharField(max_length=255, blank=True, default='')
    approved_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'documents_checklist'
        ordering = ('-created_at',)
