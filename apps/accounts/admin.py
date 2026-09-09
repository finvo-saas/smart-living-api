from django.contrib import admin

from accounts.models import (
    AdminProfile,
    OTPChallenge,
    RoommateProfile,
    TrustedDevice,
    User,
    UserProfile,
    VerificationDocument,
)
from accounts.phone import normalize_bd_phone
from core.exceptions import InvalidError


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'phone',
        'name',
        'role',
        'role_selected',
        'owner_primary_focus',
        'owner_focus_selected',
        'is_phone_verified',
        'pin_set_at',
        'is_active',
        'created_at',
    )
    list_filter = (
        'role',
        'role_selected',
        'owner_primary_focus',
        'owner_focus_selected',
        'is_phone_verified',
        'is_active',
    )
    search_fields = ('phone', 'whatsapp_number', 'name', 'email')
    ordering = ('-created_at',)

    def save_model(self, request, obj, form, change):
        if obj.phone:
            try:
                obj.phone = normalize_bd_phone(obj.phone)
            except InvalidError as exc:
                from django.core.exceptions import ValidationError

                raise ValidationError({'phone': str(exc)}) from exc
        super().save_model(request, obj, form, change)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    search_fields = ('user__phone', 'user__name')


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'admin_role', 'is_active', 'created_at')
    list_filter = ('admin_role', 'is_active')
    search_fields = ('user__phone',)


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = ('phone', 'purpose', 'attempts', 'expires_at', 'consumed_at', 'created_at')
    list_filter = ('purpose',)
    search_fields = ('phone',)
    readonly_fields = ('code_hash',)


@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'verification_type',
        'document_number',
        'status',
        'created_at',
        'reviewed_at',
    )
    list_filter = ('verification_type', 'status')
    search_fields = ('user__phone', 'document_number')


@admin.register(RoommateProfile)
class RoommateProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'looking', 'city', 'occupation', 'updated_at')
    list_filter = ('looking', 'occupation', 'city')
    search_fields = ('user__phone', 'user__name', 'city', 'area')


@admin.register(TrustedDevice)
class TrustedDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'expires_at',
        'last_used_at',
        'revoked_at',
        'created_at',
    )
    list_filter = ('revoked_at',)
    search_fields = ('user__phone',)
    readonly_fields = ('token_hash',)
