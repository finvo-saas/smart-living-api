"""Trusted-device tokens (hashed, httpOnly cookie)."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from accounts.models import TrustedDevice, User
from accounts.services.cookies import (
    device_cookie_name,
    set_device_cookie,
)


def _hash_token(token: str) -> str:
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, token.encode(), hashlib.sha256).hexdigest()


def resolve_trusted_device(request, user: User | None) -> TrustedDevice | None:
    if user is None:
        return None
    raw = request.COOKIES.get(device_cookie_name()) or ''
    if not raw:
        return None
    now = timezone.now()
    device = (
        TrustedDevice.objects.filter(
            user=user,
            token_hash=_hash_token(raw),
            revoked_at__isnull=True,
            expires_at__gt=now,
        )
        .first()
    )
    if device is None:
        return None
    device.last_used_at = now
    device.save(update_fields=['last_used_at'])
    return device


def issue_trusted_device(response, user: User, request) -> None:
    """Reuse a still-valid device cookie, otherwise mint a new one."""
    existing = resolve_trusted_device(request, user)
    days = int(getattr(settings, 'AUTH_DEVICE_TTL_DAYS', 90))
    now = timezone.now()
    expires = now + timedelta(days=days)
    agent = (request.META.get('HTTP_USER_AGENT') or '')[:256]

    if existing is not None:
        existing.expires_at = expires
        existing.last_used_at = now
        existing.user_agent = agent
        existing.save(update_fields=['expires_at', 'last_used_at', 'user_agent', 'updated_at'])
        raw = request.COOKIES.get(device_cookie_name()) or ''
        if raw:
            set_device_cookie(response, raw)
        return

    raw = secrets.token_urlsafe(32)
    TrustedDevice.objects.create(
        user=user,
        token_hash=_hash_token(raw),
        expires_at=expires,
        last_used_at=now,
        user_agent=agent,
    )
    set_device_cookie(response, raw)
