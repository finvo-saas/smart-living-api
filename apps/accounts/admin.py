from django.contrib import admin

from accounts.models import (
    AdminProfile,
    OTPChallenge,
    User,
    UserProfile,
    VerificationDocument,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        'phone',
        'name',
        'role',
        'role_selected',
        'is_phone_verified',
        'is_active',
        'created_at',
    )
    list_filter = ('role', 'role_selected', 'is_phone_verified', 'is_active')
    search_fields = ('phone', 'name', 'email')
    ordering = ('-created_at',)


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
