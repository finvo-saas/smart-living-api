"""Bangladesh phone normalization helpers."""

import re

from core.exceptions import InvalidError

PHONE_DIGITS_RE = re.compile(r'\D+')


def normalize_bd_phone(raw: str) -> str:
    """
    Normalize to E.164 Bangladesh mobile: +8801XXXXXXXXX

    Accepts: 8801..., +8801..., 01..., 1...
    """
    if not raw or not str(raw).strip():
        raise InvalidError('Phone number is required.')

    digits = PHONE_DIGITS_RE.sub('', str(raw).strip())

    if digits.startswith('880') and len(digits) == 13 and digits[3] == '1':
        return f'+{digits}'
    if digits.startswith('0') and len(digits) == 11 and digits[1] == '1':
        return f'+880{digits[1:]}'
    if len(digits) == 10 and digits.startswith('1'):
        return f'+880{digits}'

    raise InvalidError('Enter a valid Bangladesh mobile number (+8801XXXXXXXXX).')


def phone_digits(e164: str) -> str:
    """Return digits only (8801XXXXXXXXX) for frontend sessionStorage."""
    return PHONE_DIGITS_RE.sub('', e164)


def phone_lookup_variants(raw: str | None) -> set[str]:
    """
    All common BD forms of one mobile number for DB matching.

    Owners may save ``0199…`` while login stores ``+880199…``.
    """
    if not raw or not str(raw).strip():
        return set()
    text = str(raw).strip()
    variants = {text}
    digits = PHONE_DIGITS_RE.sub('', text)
    if digits:
        variants.add(digits)
    try:
        e164 = normalize_bd_phone(text)
    except InvalidError:
        return {v for v in variants if v}

    variants.add(e164)
    e164_digits = PHONE_DIGITS_RE.sub('', e164)
    variants.add(e164_digits)
    variants.add(f'+{e164_digits}')
    if len(e164_digits) >= 10:
        local = f'0{e164_digits[-10:]}'
        variants.add(local)
        variants.add(e164_digits[-10:])
    return {v for v in variants if v}
