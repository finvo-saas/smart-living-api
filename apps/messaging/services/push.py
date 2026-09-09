"""Web Push (VAPID) delivery and admin-configurable policy."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.utils import timezone

from messaging.models import Notification, NotificationType, PushSubscription

logger = logging.getLogger('messaging.push')

DEFAULT_PUSH: dict[str, Any] = {
    'enabled': True,
    'heartbeatEnabled': True,
    'preferPushOverSms': True,
    'smsIfPushFails': True,
    'titleTemplate': 'Still available? {name}',
    'bodyTemplate': 'Tap to confirm {name} in {city}. Valid {hours}h.',
    'iconPath': '/icons/icon.svg',
}


def default_push_config() -> dict[str, Any]:
    return dict(DEFAULT_PUSH)


def merge_push_config(raw: dict | None) -> dict[str, Any]:
    merged = default_push_config()
    if not isinstance(raw, dict):
        return merged
    for key, default in DEFAULT_PUSH.items():
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if isinstance(default, bool):
            merged[key] = bool(value)
        elif isinstance(default, str):
            merged[key] = str(value)
        else:
            merged[key] = value
    return merged


def get_push_config() -> dict[str, Any]:
    from admin_api.models import SystemSettings

    row = SystemSettings.load()
    return merge_push_config(getattr(row, 'push', None) or {})


def vapid_public_key() -> str:
    return str(getattr(settings, 'VAPID_PUBLIC_KEY', '') or '').strip()


def vapid_private_key() -> str:
    return str(getattr(settings, 'VAPID_PRIVATE_KEY', '') or '').strip()


def vapid_subject() -> str:
    return str(
        getattr(settings, 'VAPID_SUBJECT', '')
        or 'mailto:support@smartbasa.local',
    ).strip()


def env_push_enabled() -> bool:
    return bool(getattr(settings, 'PUSH_ENABLED', True))


def is_push_configured() -> bool:
    return bool(vapid_public_key() and vapid_private_key())


def should_send_push(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or get_push_config()
    return bool(cfg.get('enabled')) and env_push_enabled() and is_push_configured()


def _render(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def create_in_app_notification(user, *, title: str, body: str, url: str = '', ntype: str = '') -> Notification:
    return Notification.objects.create(
        user=user,
        title=title[:255],
        message=body,
        type=ntype or NotificationType.PUSH,
        link=(url or '')[:200],
    )


def send_web_push(
    user,
    *,
    title: str,
    body: str,
    url: str = '/',
    tag: str = 'smart-living',
) -> dict:
    """Send to all of the user's browser subscriptions. Returns counts."""
    cfg = get_push_config()
    result = {'attempted': 0, 'sent': 0, 'failed': 0, 'removed': 0}
    if not should_send_push(cfg):
        return result
    if not getattr(user, 'push_opt_in', True):
        return result

    subs = list(PushSubscription.objects.filter(user=user))
    if not subs:
        return result

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning('pywebpush is not installed; cannot send web push.')
        return result

    payload = json.dumps(
        {
            'title': title,
            'body': body,
            'url': url,
            'tag': tag,
            'icon': cfg.get('iconPath') or '/icons/icon.svg',
        },
    )
    claims = {'sub': vapid_subject()}
    private = vapid_private_key()

    for sub in subs:
        result['attempted'] += 1
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=private,
                vapid_claims=claims,
            )
            sub.last_seen_at = timezone.now()
            sub.fail_count = 0
            sub.save(update_fields=['last_seen_at', 'fail_count', 'updated_at'])
            result['sent'] += 1
        except WebPushException as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            logger.info('Web push failed user=%s status=%s', user.id, status)
            if status in (404, 410):
                sub.delete()
                result['removed'] += 1
            else:
                sub.fail_count = (sub.fail_count or 0) + 1
                sub.save(update_fields=['fail_count', 'updated_at'])
                result['failed'] += 1
        except Exception:  # noqa: BLE001
            logger.exception('Web push error user=%s', user.id)
            result['failed'] += 1

    return result


def notify_user(
    user,
    *,
    title: str,
    body: str,
    url: str = '/',
    tag: str = 'smart-living',
    ntype: str = '',
) -> dict:
    """In-app row + web push."""
    create_in_app_notification(user, title=title, body=body, url=url, ntype=ntype)
    return send_web_push(user, title=title, body=body, url=url, tag=tag)


def push_stats() -> dict:
    from accounts.models import User

    cfg = get_push_config()
    return {
        'config': cfg,
        'configured': is_push_configured(),
        'envEnabled': env_push_enabled(),
        'liveWouldSend': should_send_push(cfg),
        'subscribers': PushSubscription.objects.values('user_id').distinct().count(),
        'devices': PushSubscription.objects.count(),
        'optedOutUsers': User.objects.filter(push_opt_in=False).count(),
    }
