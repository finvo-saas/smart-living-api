from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from accounts.managers import UserManager
from core.models import TimestampedModel, UUIDModel


class Role(models.TextChoices):
    RENTER = 'renter', 'Renter'
    OWNER = 'owner', 'Owner'
    ADMIN = 'admin', 'Admin'


class User(AbstractBaseUser, UUIDModel, TimestampedModel, PermissionsMixin):
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, default='')
    name = models.CharField(max_length=255, blank=True, default='')
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RENTER,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    profile_photo = models.ImageField(upload_to='profiles/', null=True, blank=True)
    locale = models.CharField(max_length=5, default='en')
    role_selected = models.BooleanField(
        default=False,
        help_text='False until user completes role selection after first OTP login.',
    )

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return self.phone

    @property
    def admin_role(self):
        profile = getattr(self, 'admin_profile', None)
        return profile.admin_role if profile else None


class OTPChallenge(UUIDModel, TimestampedModel):
    class Purpose(models.TextChoices):
        LOGIN = 'login', 'Login'
        PHONE_CHANGE = 'phone_change', 'Phone change'
        RECOVER = 'recover', 'Account recover'

    phone = models.CharField(max_length=20, db_index=True)
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='otp_challenges',
    )

    class Meta:
        db_table = 'accounts_otp_challenge'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['phone', 'purpose', '-created_at']),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None


class UserProfile(UUIDModel, TimestampedModel):
    """Extended profile data (maps to frontend RenterProfile shape)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    job_info = models.JSONField(default=dict, blank=True)
    family_members = models.JSONField(default=list, blank=True)
    emergency_contacts = models.JSONField(default=list, blank=True)
    documents = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'accounts_user_profile'

    def __str__(self):
        return f'Profile<{self.user.phone}>'


class AdminProfile(UUIDModel, TimestampedModel):
    class AdminRole(models.TextChoices):
        SUPER_ADMIN = 'super-admin', 'Super Admin'
        MODERATOR = 'moderator', 'Moderator'
        SUPPORT = 'support', 'Support'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_profile',
    )
    admin_role = models.CharField(max_length=32, choices=AdminRole.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'accounts_admin_profile'

    def __str__(self):
        return f'{self.user.phone} ({self.admin_role})'


class VerificationDocument(UUIDModel, TimestampedModel):
    class VerificationType(models.TextChoices):
        NID = 'nid', 'NID'
        PHONE = 'phone', 'Phone'
        DOCUMENT = 'document', 'Document'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_documents',
    )
    verification_type = models.CharField(
        max_length=20,
        choices=VerificationType.choices,
    )
    document_number = models.CharField(max_length=64, blank=True, default='')
    file = models.FileField(upload_to='verification/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_verifications',
    )
    rejection_reason = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'accounts_verification_document'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.verification_type}:{self.user.phone}:{self.status}'
