from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


class DisputeStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    ASSIGNED = 'assigned', 'Assigned'
    IN_PROGRESS = 'in_progress', 'In Progress'
    RESOLVED = 'resolved', 'Resolved'
    CLOSED = 'closed', 'Closed'


class DisputeType(models.TextChoices):
    PAYMENT = 'payment', 'Payment'
    PROPERTY = 'property', 'Property'
    BOOKING = 'booking', 'Booking'
    OTHER = 'other', 'Other'


class DisputePriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class Dispute(UUIDModel, TimestampedModel):
    title = models.CharField(max_length=255)
    description = models.TextField()
    type = models.CharField(max_length=20, choices=DisputeType.choices, default=DisputeType.OTHER)
    status = models.CharField(
        max_length=20,
        choices=DisputeStatus.choices,
        default=DisputeStatus.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=20,
        choices=DisputePriority.choices,
        default=DisputePriority.MEDIUM,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_disputes',
    )
    created_by_name = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_disputes',
    )
    assigned_to_name = models.CharField(max_length=255, blank=True, default='')
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_disputes',
    )
    related_property_id = models.UUIDField(null=True, blank=True)
    related_booking_id = models.UUIDField(null=True, blank=True)
    evidence = models.JSONField(default=list, blank=True)
    resolution = models.TextField(blank=True, default='')
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'admin_api_dispute'
        ordering = ('-created_at',)

    def __str__(self):
        return self.title


class FraudReportType(models.TextChoices):
    SUSPICIOUS_ACTIVITY = 'suspicious_activity', 'Suspicious Activity'
    FAKE_LISTING = 'fake_listing', 'Fake Listing'
    PAYMENT_FRAUD = 'payment_fraud', 'Payment Fraud'
    OTHER = 'other', 'Other'


class FraudReportStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    INVESTIGATING = 'investigating', 'Investigating'
    RESOLVED = 'resolved', 'Resolved'
    DISMISSED = 'dismissed', 'Dismissed'


class FraudReport(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fraud_reports',
    )
    user_name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=32, choices=FraudReportType.choices)
    description = models.TextField()
    evidence = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=FraudReportStatus.choices,
        default=FraudReportStatus.PENDING,
        db_index=True,
    )
    investigated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='investigated_fraud_reports',
    )
    resolution = models.TextField(blank=True, default='')
    priority = models.CharField(
        max_length=20,
        choices=DisputePriority.choices,
        default=DisputePriority.MEDIUM,
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'admin_api_fraud_report'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.report_type}:{self.user_name}'


class ActivityResourceType(models.TextChoices):
    USER = 'user', 'User'
    PROPERTY = 'property', 'Property'
    BOOKING = 'booking', 'Booking'
    COMPLAINT = 'complaint', 'Complaint'
    DISPUTE = 'dispute', 'Dispute'


class ActivityLog(UUIDModel, TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    user_name = models.CharField(max_length=255)
    action = models.CharField(max_length=64)
    resource_type = models.CharField(max_length=20, choices=ActivityResourceType.choices)
    resource_id = models.CharField(max_length=64)
    details = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')

    class Meta:
        db_table = 'admin_api_activity_log'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.action}:{self.resource_type}:{self.resource_id}'


class UserAccountStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    BANNED = 'banned', 'Banned'


class UserModeration(UUIDModel, TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='moderation',
    )
    status = models.CharField(
        max_length=20,
        choices=UserAccountStatus.choices,
        default=UserAccountStatus.ACTIVE,
        db_index=True,
    )
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'admin_api_user_moderation'

    def __str__(self):
        return f'{self.user.phone}:{self.status}'


class SystemSettings(models.Model):
    """Singleton platform settings row (pk=1)."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    platform_name = models.CharField(max_length=120, default='Smart Living')
    platform_email = models.EmailField(blank=True, default='support@smartliving.com')
    platform_phone = models.CharField(max_length=20, blank=True, default='+8801712345678')
    commission_rate = models.FloatField(default=5.0)
    subscription_plans = models.JSONField(default=dict, blank=True)
    feature_flags = models.JSONField(default=dict, blank=True)
    sms_gateway = models.JSONField(default=dict, blank=True)
    email_service = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'admin_api_system_settings'
        verbose_name_plural = 'System settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.platform_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
