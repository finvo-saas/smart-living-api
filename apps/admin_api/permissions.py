from rest_framework.permissions import BasePermission

# Mirrors frontend lib/admin/permissions.ts
ROLE_PERMISSIONS = {
    'super-admin': {
        'dashboard.view',
        'users.view',
        'users.manage',
        'users.ban',
        'properties.moderate',
        'bookings.view',
        'bookings.manage',
        'complaints.manage',
        'verifications.manage',
        'disputes.manage',
        'fraud.manage',
        'analytics.view',
        'settings.manage',
        'audit.view',
    },
    'moderator': {
        'dashboard.view',
        'users.view',
        'users.manage',
        'properties.moderate',
        'bookings.view',
        'bookings.manage',
        'complaints.manage',
        'verifications.manage',
        'disputes.manage',
        'fraud.manage',
        'analytics.view',
        'audit.view',
    },
    'support': {
        'dashboard.view',
        'complaints.manage',
        'verifications.manage',
        'disputes.manage',
        'bookings.view',
        'fraud.manage',
    },
}


def admin_has_permission(admin_role: str | None, permission: str) -> bool:
    if not admin_role:
        return False
    return permission in ROLE_PERMISSIONS.get(admin_role, set())


class IsPlatformAdmin(BasePermission):
    """
    Require platform admin role with an active AdminProfile.
    When the view sets `admin_permission`, also enforce fine-grained role ACL.
    """

    message = 'Platform admin access required.'

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or user.role != 'admin':
            return False
        profile = getattr(user, 'admin_profile', None)
        if profile is None or not profile.is_active:
            return False

        required = getattr(view, 'admin_permission', None)
        if required:
            if not admin_has_permission(profile.admin_role, required):
                self.message = f'Missing admin permission: {required}'
                return False
        return True


class HasAdminPermission(IsPlatformAdmin):
    """Alias used in design docs — same behavior as IsPlatformAdmin."""
