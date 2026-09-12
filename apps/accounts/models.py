from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from accounts.managers import UserManager
from core.models import TimestampedModel, UUIDModel
from core.services.media import upload_to_profile, upload_to_verification
from core.storage import private_media_storage


class Role(models.TextChoices):
    RENTER = 'renter', 'Renter'
    OWNER = 'owner', 'Owner'
    ADMIN = 'admin', 'Admin'


class OwnerVertical(models.TextChoices):
    MESS = 'mess', 'Mess / Hostel'
    APARTMENT = 'apartment', 'Apartment / Building'
    HOTEL = 'hotel', 'Hotel'


class User(AbstractBaseUser, UUIDModel, TimestampedModel, PermissionsMixin):
    phone = models.CharField(max_length=20, unique=True)
    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='WhatsApp mobile number (E.164). Blank means no WhatsApp contact.',
    )
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
    profile_photo = models.ImageField(
        upload_to=upload_to_profile,
        null=True,
        blank=True,
    )
    locale = models.CharField(max_length=5, default='en')
    role_selected = models.BooleanField(
        default=False,
        help_text='False until user completes role selection after first OTP login.',
    )
    pin_set_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set when the user stores a 4–6 digit PIN (Django password hash).',
    )
    heartbeat_sms_opt_in = models.BooleanField(
        default=True,
        help_text='Owners receive weekly vacancy-confirm SMS when enabled by admin.',
    )
    push_opt_in = models.BooleanField(
        default=True,
        help_text='Browser/web-app push notifications when the user has subscribed.',
    )
    # Owner business focus — hide unused verticals (mess / apartment / hotel)
    owner_primary_focus = models.CharField(
        max_length=20,
        blank=True,
        default='',
        choices=OwnerVertical.choices,
        help_text='Primary business type for dashboard defaults.',
    )
    owner_enabled_verticals = models.JSONField(
        default=list,
        blank=True,
        help_text='Enabled owner verticals: mess, apartment, hotel.',
    )
    owner_focus_selected = models.BooleanField(
        default=False,
        help_text='True after the owner completes business-focus onboarding.',
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

    def save(self, *args, **kwargs):
        # Always store E.164 (+8801XXXXXXXXX) — prevents 01… / +880… duplicates
        from accounts.phone import normalize_bd_phone

        if self.phone:
            self.phone = normalize_bd_phone(self.phone)
        if self.whatsapp_number:
            self.whatsapp_number = normalize_bd_phone(self.whatsapp_number)
        return super().save(*args, **kwargs)

    @property
    def admin_role(self):
        profile = getattr(self, 'admin_profile', None)
        return profile.admin_role if profile else None

    @property
    def has_pin(self) -> bool:
        return self.pin_set_at is not None

    def owner_verticals_list(self) -> list[str]:
        raw = self.owner_enabled_verticals or []
        if not isinstance(raw, list):
            return []
        allowed = {c.value for c in OwnerVertical}
        verticals = [str(v) for v in raw if str(v) in allowed]
        if len(verticals) <= 1:
            return verticals
        # Single-business policy: prefer primary when valid.
        primary = self.owner_primary_focus or ''
        if primary in verticals:
            return [primary]
        return [verticals[0]]

    def has_owner_vertical(self, vertical: str) -> bool:
        if self.role != Role.OWNER:
            return False
        if not self.owner_focus_selected:
            # Until they choose, treat as unfocused (UI forces picker).
            return False
        return vertical in self.owner_verticals_list()


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
    # CIMS compliance (DMP Dhaka Metropolitan Police)
    cims_registered = models.BooleanField(
        default=False,
        help_text='Whether user has registered with CIMS (DMP).',
    )
    cims_registration_number = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='CIMS registration reference number.',
    )
    cims_police_station = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Thana / police station for CIMS registration.',
    )
    cims_registered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date when CIMS registration was completed.',
    )
    cims_reminder_dismissed = models.BooleanField(
        default=False,
        help_text='User dismissed the CIMS registration reminder.',
    )

    class Meta:
        db_table = 'accounts_user_profile'

    def __str__(self):
        return f'Profile<{self.user.phone}>'


class RoommateProfile(UUIDModel, TimestampedModel):
    """Lifestyle questionnaire used for AI roommate matching."""

    class Occupation(models.TextChoices):
        STUDENT = 'student', 'Student'
        JOB = 'job', 'Job'
        OTHER = 'other', 'Other'

    class SleepSchedule(models.TextChoices):
        EARLY = 'early', 'Early bird'
        NORMAL = 'normal', 'Normal'
        LATE = 'late', 'Night owl'

    class Social(models.TextChoices):
        QUIET = 'quiet', 'Quiet'
        BALANCED = 'balanced', 'Balanced'
        CHATTY = 'chatty', 'Social'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'

    class GenderPref(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        ANY = 'any', 'Any'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='roommate_profile',
    )
    looking = models.BooleanField(default=True, db_index=True)
    occupation = models.CharField(
        max_length=20,
        choices=Occupation.choices,
        default=Occupation.STUDENT,
    )
    sleep_schedule = models.CharField(
        max_length=20,
        choices=SleepSchedule.choices,
        default=SleepSchedule.NORMAL,
    )
    smoking = models.BooleanField(default=False)
    cooking = models.BooleanField(default=True)
    cleanliness = models.PositiveSmallIntegerField(default=3)
    social = models.CharField(
        max_length=20,
        choices=Social.choices,
        default=Social.BALANCED,
    )
    pets_ok = models.BooleanField(default=False)
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        blank=True,
        default='',
    )
    gender_pref = models.CharField(
        max_length=20,
        choices=GenderPref.choices,
        default=GenderPref.ANY,
    )
    city = models.CharField(max_length=80, blank=True, default='', db_index=True)
    area = models.CharField(max_length=120, blank=True, default='')
    budget_min = models.PositiveIntegerField(default=0)
    budget_max = models.PositiveIntegerField(default=0)
    bio = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'accounts_roommate_profile'

    def __str__(self):
        return f'Roommate<{self.user.phone}>'


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
        POLICE = 'police', 'Police verification'

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
    file = models.FileField(
        upload_to=upload_to_verification,
        storage=private_media_storage,
        null=True,
        blank=True,
    )
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


class TrustedDevice(UUIDModel, TimestampedModel):
    """Browser remembered after OTP or PIN login (httpOnly device cookie)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trusted_devices',
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    user_agent = models.CharField(max_length=256, blank=True, default='')
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'accounts_trusted_device'
        ordering = ('-last_used_at', '-created_at')

    def __str__(self):
        return f'Device<{self.user.phone}>'

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return timezone.now() < self.expires_at
