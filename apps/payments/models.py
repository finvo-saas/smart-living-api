from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


class PaymentMethod(models.TextChoices):
    BKASH = 'bKash', 'bKash'
    NAGAD = 'Nagad', 'Nagad'
    ROCKET = 'Rocket', 'Rocket'
    BANK_TRANSFER = 'Bank Transfer', 'Bank Transfer'
    CASH = 'Cash', 'Cash'
    CARD = 'Card', 'Card'


class PaymentTransactionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class ScheduledPaymentStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class PayoutStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    PAID = 'paid', 'Paid'
    HELD = 'held', 'Held'


class PaymentGateway(models.TextChoices):
    BKASH = 'bkash', 'bKash'
    NAGAD = 'nagad', 'Nagad'
    ROCKET = 'rocket', 'Rocket'


class ScheduleFrequency(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    WEEKLY = 'weekly', 'Weekly'
    YEARLY = 'yearly', 'Yearly'


class PaymentTransaction(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_transactions',
    )
    bill = models.ForeignKey(
        'billing.Bill',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_transactions',
    )
    bill_name = models.CharField(max_length=255)
    property_name = models.CharField(max_length=255, blank=True, default='')
    tenant_name = models.CharField(max_length=255, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    account_number = models.CharField(max_length=64, blank=True, default='')
    transaction_id = models.CharField(max_length=128, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentTransactionStatus.choices,
        default=PaymentTransactionStatus.PENDING,
    )
    failure_reason = models.TextField(blank=True, default='')
    receipt_note = models.TextField(blank=True, default='')
    receipt_file_name = models.CharField(max_length=255, blank=True, default='')
    completed_at = models.DateTimeField(null=True, blank=True)
    gateway_payload = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        unique=True,
    )

    class Meta:
        db_table = 'payments_transaction'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['transaction_id']),
        ]

    def __str__(self):
        return f'{self.transaction_id} ({self.status})'


class ScheduledPayment(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='scheduled_payments',
    )
    bill = models.ForeignKey(
        'billing.Bill',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_payments',
    )
    bill_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    scheduled_date = models.DateField()
    scheduled_time = models.CharField(max_length=8, blank=True, default='')
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    account_number = models.CharField(max_length=64, blank=True, default='')
    transaction_id = models.CharField(max_length=128, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=ScheduledPaymentStatus.choices,
        default=ScheduledPaymentStatus.SCHEDULED,
    )
    reminder_enabled = models.BooleanField(default=True)
    reminder_days = models.JSONField(default=list, blank=True)
    auto_retry = models.BooleanField(default=False)
    max_retries = models.PositiveIntegerField(default=0)
    retry_count = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'payments_scheduled'
        ordering = ['scheduled_date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f'{self.bill_name} on {self.scheduled_date}'


class PaymentSchedule(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_schedules',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    bill = models.ForeignKey(
        'billing.Bill',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_schedules',
    )
    recurring = models.BooleanField(default=False)
    frequency = models.CharField(
        max_length=20,
        choices=ScheduleFrequency.choices,
        blank=True,
        default='',
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reminder_enabled = models.BooleanField(default=True)
    reminder_days = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'payments_schedule'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class OwnerPayout(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owner_payouts',
    )
    bill = models.ForeignKey(
        'billing.Bill',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owner_payouts',
    )
    payment_transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owner_payouts',
    )
    bill_name = models.CharField(max_length=255)
    tenant_name = models.CharField(max_length=255)
    property_name = models.CharField(max_length=255)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text='Percent for display, e.g. 5.0 for 5%',
    )
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    transaction_id = models.CharField(max_length=128, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payout_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'payments_owner_payout'
        ordering = ['-paid_at', '-created_at']
        indexes = [
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self):
        return f'{self.bill_name} — {self.net_amount}'


class PaymentWebhookEvent(UUIDModel, TimestampedModel):
    gateway = models.CharField(max_length=20, choices=PaymentGateway.choices)
    gateway_event_id = models.CharField(max_length=255, unique=True)
    raw_payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    payment_transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='webhook_events',
    )

    class Meta:
        db_table = 'payments_webhook_event'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.gateway}:{self.gateway_event_id}'


class CollectionMode(models.TextChoices):
    """How rent/dues money moves — platform never holds money by default."""

    MANUAL = 'manual', 'Manual ledger (owner collects)'
    OWNER_GATEWAY = 'owner_gateway', 'Owner merchant gateway'
    PLATFORM_COLLECT = 'platform_collect', 'Platform collects (opt-in managed)'


class PaymentClaimStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    REJECTED = 'rejected', 'Rejected'


class OwnerCollectionSettings(UUIDModel, TimestampedModel):
    """Owner payment instructions + collection mode (BD: owner holds the money)."""

    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='collection_settings',
    )
    collection_mode = models.CharField(
        max_length=32,
        choices=CollectionMode.choices,
        default=CollectionMode.MANUAL,
        db_index=True,
    )
    platform_collect_enabled = models.BooleanField(
        default=False,
        help_text='Opt-in managed collect (hotels/NRB). Never default for mess/flats.',
    )
    bkash_number = models.CharField(max_length=32, blank=True, default='')
    nagad_number = models.CharField(max_length=32, blank=True, default='')
    rocket_number = models.CharField(max_length=32, blank=True, default='')
    bank_name = models.CharField(max_length=120, blank=True, default='')
    bank_account_number = models.CharField(max_length=64, blank=True, default='')
    bank_account_name = models.CharField(max_length=120, blank=True, default='')
    payment_note = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'payments_owner_collection_settings'

    def __str__(self):
        return f'CollectionSettings({self.owner_id})'


class OwnerGatewayCredential(UUIDModel, TimestampedModel):
    """Owner's own merchant credentials — settlements go to the owner, not the platform."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gateway_credentials',
    )
    gateway = models.CharField(max_length=20, choices=PaymentGateway.choices)
    display_name = models.CharField(max_length=120, blank=True, default='')
    merchant_number = models.CharField(max_length=64, blank=True, default='')
    credentials = models.JSONField(
        default=dict,
        blank=True,
        help_text='Merchant API keys (never expose full secrets to clients).',
    )
    is_active = models.BooleanField(default=True)
    is_sandbox = models.BooleanField(default=True)

    class Meta:
        db_table = 'payments_owner_gateway_credential'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'gateway'],
                name='unique_owner_gateway_credential',
            ),
        ]

    def __str__(self):
        return f'{self.owner_id}:{self.gateway}'


class PaymentClaim(UUIDModel, TimestampedModel):
    """Tenant/member says “I paid” — owner confirms before ledger credit."""

    bill = models.ForeignKey(
        'billing.Bill',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_claims',
    )
    mess = models.ForeignKey(
        'mess.Mess',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_claims',
    )
    student = models.ForeignKey(
        'mess.MessStudent',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='payment_claims',
    )
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_claims_made',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    transaction_id = models.CharField(max_length=128, blank=True, default='')
    note = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=PaymentClaimStatus.choices,
        default=PaymentClaimStatus.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_claims_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    payment_transaction = models.ForeignKey(
        PaymentTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_claims',
    )
    member_deposit = models.ForeignKey(
        'mess.MemberDeposit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_claims',
    )

    class Meta:
        db_table = 'payments_payment_claim'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Claim {self.amount} ({self.status})'
