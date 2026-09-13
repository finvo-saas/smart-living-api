"""Transactional email adapter — SMTP or console."""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail

logger = logging.getLogger('accounts.email')


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    *,
    html: str | None = None,
) -> bool:
    """
    Send transactional email. Returns True on success.
    Console provider logs only (always succeeds).
    """
    recipients = [to] if isinstance(to, str) else [r for r in to if r]
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        return False

    provider = (getattr(settings, 'EMAIL_PROVIDER', 'console') or 'console').lower()
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@smartbasa.local'

    if provider in ('console', '', 'log'):
        logger.info('EMAIL → %s | %s | %s', recipients, subject, body[:200])
        return True

    try:
        if html:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=from_email,
                to=recipients,
            )
            msg.attach_alternative(html, 'text/html')
            msg.send(fail_silently=False)
        else:
            send_mail(
                subject,
                body,
                from_email,
                recipients,
                fail_silently=False,
            )
        return True
    except Exception:
        logger.exception('Email send failed to %s', recipients)
        if settings.DEBUG:
            logger.info('EMAIL fallback (console) → %s | %s', recipients, subject)
            return True
        return False


def notify_channels(
    user,
    *,
    title: str,
    body: str,
    url: str = '/',
    email_subject: str | None = None,
    ntype: str = '',
    tag: str = 'smart-living',
) -> dict:
    """Fan-out: in-app/push via messaging, optional email, optional SMS."""
    result = {'push': False, 'email': False, 'sms': False}
    try:
        from messaging.services.push import notify_user

        notify_user(user, title=title, body=body, url=url, ntype=ntype, tag=tag)
        result['push'] = True
    except Exception:
        logger.exception('notify_user failed')

    email = getattr(user, 'email', '') or ''
    if email and getattr(settings, 'EMAIL_NOTIFY_ENABLED', True):
        result['email'] = send_email(
            email,
            email_subject or title,
            f'{body}\n\nOpen: {getattr(settings, "FRONTEND_URL", "")}{url}',
        )

    if getattr(settings, 'SMS_NOTIFY_ENABLED', False):
        phone = getattr(user, 'phone', '') or ''
        if phone:
            try:
                from accounts.services.sms import send_sms

                send_sms(phone, f'{title}: {body}'[:150])
                result['sms'] = True
            except Exception:
                logger.exception('SMS notify failed')
    return result
