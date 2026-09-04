"""4–6 digit PIN helpers (stored via Django password hasher)."""

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from core.exceptions import InvalidError

PIN_UNLOCK_SECONDS = 600


def validate_pin(pin: str) -> str:
    value = (pin or '').strip()
    if not value.isdigit() or not (4 <= len(value) <= 6):
        raise InvalidError('PIN must be 4 to 6 digits.')
    return value


def _fail_key(phone: str) -> str:
    return f'pin_fail:{phone}'


def _lock_key(phone: str) -> str:
    return f'pin_lock:{phone}'


def _unlock_key(user_id) -> str:
    return f'pin_unlock:{user_id}'


def assert_pin_not_locked(phone: str) -> None:
    if cache.get(_lock_key(phone)):
        raise InvalidError('Too many PIN attempts. Try again later.')


def record_pin_failure(phone: str) -> None:
    max_attempts = int(getattr(settings, 'PIN_MAX_ATTEMPTS', 5))
    lock_seconds = int(getattr(settings, 'PIN_LOCK_SECONDS', 900))
    key = _fail_key(phone)
    count = int(cache.get(key) or 0) + 1
    cache.set(key, count, lock_seconds)
    if count >= max_attempts:
        cache.set(_lock_key(phone), 1, lock_seconds)
        raise InvalidError('Too many PIN attempts. Try again later.')
    raise InvalidError('Incorrect PIN.')


def clear_pin_failures(phone: str) -> None:
    cache.delete(_fail_key(phone))
    cache.delete(_lock_key(phone))


def grant_pin_unlock(user_id) -> None:
    """Allow replacing PIN without the current PIN (after OTP)."""
    cache.set(_unlock_key(user_id), 1, PIN_UNLOCK_SECONDS)


def can_set_pin_without_current(user) -> bool:
    return bool(cache.get(_unlock_key(user.pk)))


def set_user_pin(user, pin: str) -> None:
    user.set_password(validate_pin(pin))
    user.pin_set_at = timezone.now()
    user.save(update_fields=['password', 'pin_set_at', 'updated_at'])
    cache.delete(_unlock_key(user.pk))
