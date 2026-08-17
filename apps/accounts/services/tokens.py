"""JWT issuance with custom claims."""

from rest_framework_simplejwt.tokens import RefreshToken


def issue_tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['phone'] = user.phone
    admin_role = user.admin_role
    if admin_role:
        refresh['admin_role'] = admin_role

    access = refresh.access_token
    access['role'] = user.role
    access['phone'] = user.phone
    if admin_role:
        access['admin_role'] = admin_role

    return {
        'access': str(access),
        'refresh': str(refresh),
    }
