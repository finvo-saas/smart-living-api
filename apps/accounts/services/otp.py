"""OTP challenge lifecycle."""

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from accounts.models import OTPChallenge
from accounts.services.sms import send_sms
from core.exceptions import InvalidError

OTP_LENGTH = 6
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()


def _rate_key(phone: str, purpose: str) -> str:
    return f'otp_rate:{purpose}:{phone}'


def _check_rate_limit(phone: str, purpose: str) -> None:
    if not getattr(settings, 'OTP_RATE_LIMIT_ENABLED', True):
        return
    limit = int(getattr(settings, 'OTP_RATE_LIMIT', 5))
    window = int(getattr(settings, 'OTP_RATE_WINDOW_SECONDS', 3600))
    key = _rate_key(phone, purpose)
    count = cache.get(key, 0)
    if count >= limit:
        raise InvalidError('Too many OTP requests. Try again later.')
    if count == 0:
        cache.set(key, 1, timeout=window)
    else:
        cache.incr(key)


def _sms_provider() -> str:
    return (getattr(settings, 'SMS_PROVIDER', 'console') or 'console').lower()


def _generate_code(*, real_sms: bool) -> str:
    """
    Real BulkSMSBD delivery → always random 6-digit code.
    Console / local-only → optional fixed DEBUG code for easy testing.
    """
    if real_sms:
        return f'{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}'
    fixed = (getattr(settings, 'OTP_DEV_FIXED_CODE', '') or '').strip()
    if settings.DEBUG and fixed and len(fixed) == OTP_LENGTH and fixed.isdigit():
        return fixed
    return f'{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}'


def _otp_message(code: str) -> str:
    brand = (
        getattr(settings, 'OTP_SMS_PREFIX', '')
        or getattr(settings, 'SMS_BRAND_NAME', '')
        or 'SmartLiving'
    ).strip() or 'SmartLiving'
    minutes = OTP_TTL_SECONDS // 60
    return f'{brand}: Your verification code is {code}. Valid for {minutes} minutes.'


def request_otp(
    *,
    phone: str,
    purpose: str,
    user=None,
) -> dict:
    """
    Create OTP challenge and send SMS.

    Returns public payload. Includes `dev_otp` only when the code was NOT
    delivered by a live SMS gateway (console / DEBUG fallback) so the UI
    can autofill for local testing.
    """
    _check_rate_limit(phone, purpose)

    provider = _sms_provider()
    real_sms = provider in ('bulksmsbd', 'bulksms', 'bulksmsbd.net')
    code = _generate_code(real_sms=real_sms)
    now = timezone.now()

    # Invalidate prior unused challenges for same phone+purpose
    OTPChallenge.objects.filter(
        phone=phone,
        purpose=purpose,
        consumed_at__isnull=True,
        expires_at__gt=now,
    ).update(consumed_at=now)

    challenge = OTPChallenge.objects.create(
        phone=phone,
        code_hash=_hash_code(code),
        purpose=purpose,
        expires_at=now + timedelta(seconds=OTP_TTL_SECONDS),
        user=user,
    )

    try:
        delivery = send_sms(phone, _otp_message(code))
    except Exception:
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=['consumed_at', 'updated_at'])
        raise

    channel = (delivery or {}).get('channel', 'console')
    delivered = bool((delivery or {}).get('delivered'))

    payload = {
        'phone': phone,
        'expires_in': OTP_TTL_SECONDS,
        'purpose': purpose,
        'sms_delivered': delivered and channel != 'console',
    }
    # Autofill hint only when the user cannot read a phone SMS
    if settings.DEBUG and channel == 'console':
        payload['dev_otp'] = code
    return payload


def verify_otp(*, phone: str, code: str, purpose: str) -> OTPChallenge:
    if not code or len(str(code).strip()) != OTP_LENGTH or not str(code).isdigit():
        raise InvalidError('Enter the 6-digit OTP code.')

    challenge = (
        OTPChallenge.objects.filter(
            phone=phone,
            purpose=purpose,
            consumed_at__isnull=True,
        )
        .order_by('-created_at')
        .first()
    )

    if challenge is None:
        raise InvalidError('No active OTP. Request a new code.')

    if challenge.is_expired:
        raise InvalidError('OTP expired. Request a new code.')

    if challenge.attempts >= OTP_MAX_ATTEMPTS:
        raise InvalidError('Too many invalid attempts. Request a new code.')

    expected = challenge.code_hash
    actual = _hash_code(str(code).strip())
    if not hmac.compare_digest(expected, actual):
        challenge.attempts += 1
        challenge.save(update_fields=['attempts', 'updated_at'])
        remaining = OTP_MAX_ATTEMPTS - challenge.attempts
        raise InvalidError(
            f'Invalid OTP. {remaining} attempt(s) remaining.'
            if remaining > 0
            else 'Too many invalid attempts. Request a new code.',
        )

    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=['consumed_at', 'updated_at'])
    return challenge
