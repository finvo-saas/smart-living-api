"""SMS adapter — console stub in development."""

import logging

from django.conf import settings

logger = logging.getLogger('accounts.sms')


def send_sms(phone: str, message: str) -> None:
    provider = getattr(settings, 'SMS_PROVIDER', 'console')

    if provider == 'console':
        logger.info('SMS → %s | %s', phone, message)
        return

    # Future: Twilio / SSL Wireless / local BD gateway
    logger.warning(
        'SMS provider %r not configured; falling back to console. phone=%s message=%s',
        provider,
        phone,
        message,
    )
    logger.info('SMS → %s | %s', phone, message)
