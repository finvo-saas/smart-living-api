"""SMS adapter — BulkSMSBD in production, console in local fallback."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from core.exceptions import UnavailableError

logger = logging.getLogger('accounts.sms')

BULKSMSBD_SUCCESS_CODES = frozenset({200, 202})


def _normalize_bd_number(phone: str) -> str:
    digits = ''.join(ch for ch in phone if ch.isdigit())
    if digits.startswith('880') and len(digits) >= 13:
        return digits
    if digits.startswith('0') and len(digits) == 11:
        return f'880{digits[1:]}'
    if len(digits) == 10 and digits.startswith('1'):
        return f'880{digits}'
    return digits


def _bulksmsbd_sender_id() -> str:
    """
    BulkSMSBD requires an *approved* Sender ID from their portal.

    Prefer:
      1) BULKSMSBD_API_SENDER
      2) SMS_SENDER_ID
      3) BULKSMSBD_API_SENDER_ID (numeric non-masking IDs allowed)

    Never use API_SECRET — that is not a sender id and causes 1005 / is_masking null.
    """
    for candidate in (
        getattr(settings, 'BULKSMSBD_API_SENDER', ''),
        getattr(settings, 'SMS_SENDER_ID', ''),
        getattr(settings, 'BULKSMSBD_API_SENDER_ID', ''),
    ):
        value = (candidate or '').strip()
        if not value:
            continue
        # Masking names are short; non-masking sender numbers are typically ≤15 digits
        if value.isdigit() and 8 <= len(value) <= 15:
            return value
        if not value.isdigit() and 2 <= len(value) <= 20:
            return value
    return 'SmartBasa'


def _parse_bulksmsbd_response(raw: str) -> tuple[int | None, str]:
    text = (raw or '').strip()
    if not text:
        return None, 'Empty response from SMS gateway'
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        if text.isdigit():
            return int(text), text
        return None, text
    if isinstance(payload, dict):
        code = payload.get('response_code')
        try:
            code = int(code) if code is not None else None
        except (TypeError, ValueError):
            code = None
        message = (
            payload.get('success_message')
            or payload.get('error_message')
            or text
        )
        return code, str(message)
    return None, text


def _provider_hint(code: int | None, detail: str) -> str:
    if code == 1032:
        return (
            'Whitelist this server public IP in BulkSMSBD → Phonebook → IP White List.'
        )
    if code == 1005 or 'is_masking' in (detail or '').lower():
        return (
            'Sender ID is missing/not approved on BulkSMSBD. '
            'Set BULKSMSBD_API_SENDER to the exact Approved Sender ID from the portal '
            '(masking name or non-masking number like 88096…).'
        )
    if code in (1002, 1013, 1014, 1015):
        return 'Sender ID incorrect, disabled, or not linked to this API key.'
    if code == 1007:
        return 'BulkSMSBD balance insufficient.'
    if code == 1012:
        return 'Masking SMS must be Bengali — use a non-masking sender or Bangla text.'
    return detail[:200] if detail else 'SMS gateway rejected the request.'


def _send_bulksmsbd(phone: str, message: str) -> None:
    api_key = getattr(settings, 'SMS_API_KEY', '') or ''
    api_url = getattr(settings, 'BULKSMSBD_API_URL', '') or ''
    if not api_key or not api_url:
        raise UnavailableError('BulkSMSBD is not configured.')

    number = _normalize_bd_number(phone)
    if not number.startswith('880') or len(number) < 13:
        raise UnavailableError('SMS requires a valid Bangladesh phone number.')

    senderid = _bulksmsbd_sender_id()
    query = urllib.parse.urlencode(
        {
            'api_key': api_key,
            'type': 'text',
            'number': number,
            'senderid': senderid,
            'message': message,
        },
    )
    request = urllib.request.Request(f'{api_url}?{query}', method='GET')
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        logger.error('BulkSMSBD HTTP %s for %s: %s', exc.code, number, raw[:300])
        raise UnavailableError('Unable to send SMS. Try again.') from exc
    except urllib.error.URLError as exc:
        logger.error('BulkSMSBD network error for %s: %s', number, exc)
        raise UnavailableError('Unable to send SMS. Try again.') from exc

    code, detail = _parse_bulksmsbd_response(raw)
    if code not in BULKSMSBD_SUCCESS_CODES:
        hint = _provider_hint(code, detail)
        logger.error(
            'BulkSMSBD rejected SMS to %s senderid=%s code=%s detail=%s | %s',
            number,
            senderid,
            code,
            detail[:300],
            hint,
        )
        raise UnavailableError(f'Unable to send SMS. {hint}')
    logger.info(
        'BulkSMSBD accepted SMS to %s senderid=%s code=%s',
        number,
        senderid,
        code,
    )


def send_sms(phone: str, message: str) -> dict:
    """
    Send SMS. Returns {'channel': 'bulksmsbd'|'console', 'delivered': bool}.

    In DEBUG, BulkSMSBD failures fall back to console so local login still works,
    but callers must not treat that as a live phone delivery.
    """
    provider = (getattr(settings, 'SMS_PROVIDER', 'console') or 'console').lower()

    if provider in ('console', '', 'log'):
        logger.info('SMS → %s | %s', phone, message)
        return {'channel': 'console', 'delivered': True}

    if provider in ('bulksmsbd', 'bulksms', 'bulksmsbd.net'):
        try:
            _send_bulksmsbd(phone, message)
            return {'channel': 'bulksmsbd', 'delivered': True}
        except UnavailableError as exc:
            if settings.DEBUG:
                logger.warning(
                    'BulkSMSBD failed in DEBUG; OTP flow continues via console. '
                    'phone=%s reason=%s',
                    phone,
                    str(exc),
                )
                logger.info('SMS fallback (console) → %s | %s', phone, message)
                return {'channel': 'console', 'delivered': False}
            raise

    logger.warning(
        'Unknown SMS_PROVIDER %r; falling back to console. phone=%s',
        provider,
        phone,
    )
    logger.info('SMS → %s | %s', phone, message)
    return {'channel': 'console', 'delivered': True}
