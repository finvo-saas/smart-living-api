from django.conf import settings
from django.db import models

from core.models import TimestampedModel, UUIDModel


class AuditAction(models.TextChoices):
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    APPROVE = 'approve', 'Approve'
    REJECT = 'reject', 'Reject'
    VERIFY = 'verify', 'Verify'
    UNVERIFY = 'unverify', 'Unverify'
    PAYMENT = 'payment', 'Payment'
    ROLLBACK = 'rollback', 'Rollback'


class AuditEntityType(models.TextChoices):
    PROPERTY = 'property', 'Property'
    BUILDING = 'building', 'Building'
    FLAT = 'flat', 'Flat'
    BILL = 'bill', 'Bill'
    BOOKING = 'booking', 'Booking'
    USER = 'user', 'User'
    VERIFICATION = 'verification', 'Verification'
    DISPUTE = 'dispute', 'Dispute'
    COMPLAINT = 'complaint', 'Complaint'
    NOTICE = 'notice', 'Notice'
    MESS = 'mess', 'Mess'
    HOTEL = 'hotel', 'Hotel'
    ROOM = 'room', 'Room'


class AuditLog(UUIDModel, TimestampedModel):
    action = models.CharField(max_length=20, choices=AuditAction.choices, db_index=True)
    entity_type = models.CharField(max_length=32, choices=AuditEntityType.choices, db_index=True)
    entity_id = models.CharField(max_length=64, db_index=True)
    entity_name = models.CharField(max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    user_name = models.CharField(max_length=255, blank=True, default='')
    user_role = models.CharField(max_length=20, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    changes = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    rollback_data = models.JSONField(null=True, blank=True)
    can_rollback = models.BooleanField(default=False)
    rolled_back = models.BooleanField(default=False)

    class Meta:
        db_table = 'audit_log'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.action}:{self.entity_type}:{self.entity_id}'
