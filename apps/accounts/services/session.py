"""Build auth API payloads and set session cookies."""

from django.utils import timezone
from rest_framework.response import Response

from accounts.models import Role, User
from accounts.serializers import UserSerializer
from accounts.services.cookies import set_refresh_cookie
from accounts.services.devices import issue_trusted_device
from accounts.services.tokens import issue_tokens_for_user
from core.envelope import api_success


def user_payload(user: User, request=None) -> dict:
    return UserSerializer(user, context={'request': request}).data


def available_roles(user: User) -> list[str]:
    roles = [Role.RENTER, Role.OWNER]
    admin = getattr(user, 'admin_profile', None)
    if admin and admin.is_active:
        roles.append(Role.ADMIN)
    return roles


def auth_payload(user: User, request=None, extra: dict | None = None) -> dict:
    tokens = issue_tokens_for_user(user)
    payload = {
        'access': tokens['access'],
        'user': user_payload(user, request),
        'needsRoleSelection': not user.role_selected,
        'needsPinSetup': not user.has_pin,
        'hasPin': user.has_pin,
        'availableRoles': available_roles(user),
        'adminRole': user.admin_role,
    }
    if extra:
        payload.update(extra)
    payload['_refresh'] = tokens['refresh']
    return payload


def auth_response(
    user: User,
    request,
    *,
    remember_device: bool = True,
    extra: dict | None = None,
    status: int = 200,
):
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    # Owner-added mess members use the same phone; attach after login/signup.
    try:
        from mess.services.membership import link_user_to_mess_memberships

        link_user_to_mess_memberships(user)
    except Exception:  # noqa: BLE001 — never block auth on membership linking
        pass
    payload = auth_payload(user, request, extra=extra)
    refresh = payload.pop('_refresh')
    # Also return refresh in JSON so the SPA can refresh when the httpOnly
    # cookie is missing (Next rewrite / localhost vs 127.0.0.1 mismatches).
    payload['refresh'] = refresh
    response = Response(api_success(payload), status=status)
    set_refresh_cookie(response, refresh)
    if remember_device:
        issue_trusted_device(response, user, request)
    return response
