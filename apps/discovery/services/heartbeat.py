"""Weekly vacancy heartbeat: SMS with a public confirm link."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from accounts.services.sms import send_sms
from discovery.models import HeartbeatPing, HeartbeatStatus, HeartbeatTargetType
from discovery.services.freshness import confirm_object, flag_unavailable
from hotels.models import Hotel
from listings.models import ListingStatus, Property
from mess.models import Mess

logger = logging.getLogger('discovery.heartbeat')

DEFAULT_HEARTBEAT: dict[str, Any] = {
    'jobEnabled': True,
    'smsEnabled': False,
    'intervalDays': 7,
    'staleHideDays': 14,
    'tokenTtlHours': 72,
    'maxSmsPerOwnerPerWeek': 3,
    'weekday': 6,
    'hour': 10,
    'includeListings': True,
    'includeHotels': True,
    'includeMesses': True,
    'onlyAvailable': True,
    'publicBaseUrl': '',
    'messageTemplate': (
        'SmartLiving: Is {name} ({city}) still available? '
        'Confirm here (valid {hours}h): {url}'
    ),
}

WEEKDAY_LABELS = (
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
)


def default_heartbeat_config() -> dict[str, Any]:
    return dict(DEFAULT_HEARTBEAT)


def merge_heartbeat_config(raw: dict | None) -> dict[str, Any]:
    merged = default_heartbeat_config()
    if not isinstance(raw, dict):
        return merged
    for key, default in DEFAULT_HEARTBEAT.items():
        if key not in raw or raw[key] is None:
            continue
        value = raw[key]
        if isinstance(default, bool):
            merged[key] = bool(value)
        elif isinstance(default, int):
            try:
                merged[key] = int(value)
            except (TypeError, ValueError):
                pass
        elif isinstance(default, str):
            merged[key] = str(value)
    merged['weekday'] = max(0, min(6, int(merged['weekday'])))
    merged['hour'] = max(0, min(23, int(merged['hour'])))
    merged['intervalDays'] = max(1, min(30, int(merged['intervalDays'])))
    merged['staleHideDays'] = max(1, min(90, int(merged['staleHideDays'])))
    merged['tokenTtlHours'] = max(6, min(168, int(merged['tokenTtlHours'])))
    merged['maxSmsPerOwnerPerWeek'] = max(
        0,
        min(20, int(merged['maxSmsPerOwnerPerWeek'])),
    )
    return merged


def get_heartbeat_config() -> dict[str, Any]:
    from admin_api.models import SystemSettings

    row = SystemSettings.load()
    return merge_heartbeat_config(getattr(row, 'heartbeat', None) or {})


def public_base_url(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or get_heartbeat_config()
    raw = (
        (cfg.get('publicBaseUrl') or '').strip()
        or str(getattr(settings, 'FRONTEND_URL', '')).strip()
        or 'http://localhost:3000'
    )
    return raw.rstrip('/')


def confirm_link(token: str, cfg: dict[str, Any] | None = None) -> str:
    return f'{public_base_url(cfg)}/c/{token}'


def sms_kill_switch_on() -> bool:
    return bool(getattr(settings, 'HEARTBEAT_SMS_ENABLED', False))


def should_send_sms(cfg: dict[str, Any]) -> bool:
    return bool(cfg.get('smsEnabled')) and sms_kill_switch_on()


def in_scheduled_window(cfg: dict[str, Any]) -> bool:
    now = timezone.now().astimezone(ZoneInfo('Asia/Dhaka'))
    return now.weekday() == int(cfg['weekday']) and now.hour == int(cfg['hour'])


def load_target(target_type: str, target_id):
    mapping = {
        HeartbeatTargetType.LISTING: Property,
        'property': Property,
        HeartbeatTargetType.HOTEL: Hotel,
        HeartbeatTargetType.MESS: Mess,
    }
    model = mapping.get(target_type)
    if model is None:
        raise Property.DoesNotExist('Unknown heartbeat target.')
    return model.objects.get(pk=target_id)


def _needs_confirm(obj, interval_days: int) -> bool:
    ts = getattr(obj, 'last_confirmed_at', None)
    if ts is None:
        return True
    return ts <= timezone.now() - timedelta(days=interval_days)


def _has_open_ping(target_type: str, target_id) -> bool:
    return HeartbeatPing.objects.filter(
        target_type=target_type,
        target_id=target_id,
        status__in=[
            HeartbeatStatus.PENDING,
            HeartbeatStatus.SENT,
            HeartbeatStatus.DRY_RUN,
        ],
        expires_at__gt=timezone.now(),
    ).exists()


def _owner_opted_in(owner) -> bool:
    if owner is None or not owner.phone:
        return False
    return bool(getattr(owner, 'heartbeat_sms_opt_in', True))


def collect_candidates(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    interval = int(cfg['intervalDays'])
    only_available = bool(cfg.get('onlyAvailable', True))
    items: list[dict[str, Any]] = []

    if cfg.get('includeListings', True):
        qs = Property.objects.filter(
            published=True,
            listing_status=ListingStatus.PUBLISHED,
            flagged_unavailable_at__isnull=True,
        ).select_related('owner')
        if only_available:
            qs = qs.filter(available=True)
        for prop in qs:
            if not _owner_opted_in(prop.owner) or not _needs_confirm(prop, interval):
                continue
            if _has_open_ping(HeartbeatTargetType.LISTING, prop.id):
                continue
            items.append(
                {
                    'owner': prop.owner,
                    'target_type': HeartbeatTargetType.LISTING,
                    'target_id': prop.id,
                    'name': prop.name,
                    'city': prop.city or prop.area or '',
                },
            )

    if cfg.get('includeHotels', True):
        qs = Hotel.objects.filter(
            is_deleted=False,
            flagged_unavailable_at__isnull=True,
        ).select_related('owner')
        if only_available:
            qs = qs.filter(available_rooms__gt=0)
        for hotel in qs:
            if not _owner_opted_in(hotel.owner) or not _needs_confirm(hotel, interval):
                continue
            if _has_open_ping(HeartbeatTargetType.HOTEL, hotel.id):
                continue
            items.append(
                {
                    'owner': hotel.owner,
                    'target_type': HeartbeatTargetType.HOTEL,
                    'target_id': hotel.id,
                    'name': hotel.name,
                    'city': hotel.city or hotel.area or '',
                },
            )

    if cfg.get('includeMesses', True):
        qs = Mess.objects.filter(
            is_deleted=False,
            flagged_unavailable_at__isnull=True,
        ).select_related('owner')
        if only_available:
            qs = qs.filter(available_seats__gt=0)
        for mess in qs:
            if not _owner_opted_in(mess.owner) or not _needs_confirm(mess, interval):
                continue
            if _has_open_ping(HeartbeatTargetType.MESS, mess.id):
                continue
            items.append(
                {
                    'owner': mess.owner,
                    'target_type': HeartbeatTargetType.MESS,
                    'target_id': mess.id,
                    'name': mess.name,
                    'city': mess.city or '',
                },
            )

    return items


def _sms_sent_this_week(owner_id) -> int:
    week_ago = timezone.now() - timedelta(days=7)
    return HeartbeatPing.objects.filter(
        owner_id=owner_id,
        dry_run=False,
        sent_at__gte=week_ago,
        status__in=[
            HeartbeatStatus.SENT,
            HeartbeatStatus.CONFIRMED,
            HeartbeatStatus.MARKED_FULL,
            HeartbeatStatus.EXPIRED,
        ],
    ).count()


def _render_message(cfg: dict[str, Any], *, name: str, city: str, url: str) -> str:
    template = cfg.get('messageTemplate') or DEFAULT_HEARTBEAT['messageTemplate']
    try:
        return template.format(
            name=(name or 'your listing')[:40],
            city=city or 'BD',
            url=url,
            hours=cfg['tokenTtlHours'],
        )
    except (KeyError, IndexError, ValueError):
        return (
            f'SmartLiving: Is {name} still available? '
            f'Confirm ({cfg["tokenTtlHours"]}h): {url}'
        )


def expire_overdue_pings() -> int:
    return HeartbeatPing.objects.filter(
        status__in=[
            HeartbeatStatus.PENDING,
            HeartbeatStatus.SENT,
            HeartbeatStatus.DRY_RUN,
        ],
        expires_at__lte=timezone.now(),
    ).update(status=HeartbeatStatus.EXPIRED)


def run_heartbeat_batch(
    *,
    force: bool = False,
    send_sms_override: bool | None = None,
) -> dict:
    cfg = get_heartbeat_config()
    expired = expire_overdue_pings()

    if not force and not cfg.get('jobEnabled', True):
        return {'skipped': True, 'reason': 'job_disabled', 'expired': expired}
    if not force and not in_scheduled_window(cfg):
        return {
            'skipped': True,
            'reason': 'outside_schedule',
            'weekday': WEEKDAY_LABELS[int(cfg['weekday'])],
            'hour': cfg['hour'],
            'expired': expired,
        }

    send = should_send_sms(cfg) if send_sms_override is None else bool(send_sms_override)
    if send and not sms_kill_switch_on():
        send = False
        logger.warning('HEARTBEAT_SMS_ENABLED is false; running dry-run.')

    candidates = collect_candidates(cfg)
    cap = int(cfg['maxSmsPerOwnerPerWeek'])
    ttl = timedelta(hours=int(cfg['tokenTtlHours']))
    now = timezone.now()
    created = sent = failed = capped = 0
    sms_used: dict[str, int] = {}

    for item in candidates:
        owner = item['owner']
        owner_key = str(owner.id)
        if send and owner_key not in sms_used:
            sms_used[owner_key] = _sms_sent_this_week(owner.id)
        if send and sms_used.get(owner_key, 0) >= cap:
            capped += 1
            continue

        token = secrets.token_urlsafe(16)
        url = confirm_link(token, cfg)
        body = _render_message(
            cfg,
            name=item['name'],
            city=item['city'],
            url=url,
        )
        ping = HeartbeatPing.objects.create(
            token=token,
            owner=owner,
            target_type=item['target_type'],
            target_id=item['target_id'],
            target_name=item['name'],
            target_city=item['city'],
            expires_at=now + ttl,
            sms_body=body,
            dry_run=not send,
            channel='dry_run',
            status=HeartbeatStatus.PENDING,
        )
        created += 1

        if not send:
            ping.status = HeartbeatStatus.DRY_RUN
            ping.sent_at = now
            ping.save(update_fields=['status', 'sent_at', 'channel', 'updated_at'])
            continue

        channels: list[str] = []
        push_ok = False
        from messaging.models import NotificationType
        from messaging.services.push import get_push_config, notify_user, should_send_push

        push_cfg = get_push_config()
        if (
            should_send_push(push_cfg)
            and push_cfg.get('heartbeatEnabled')
            and getattr(owner, 'push_opt_in', True)
        ):
            ctx = {
                'name': item['name'][:40],
                'city': item['city'] or 'BD',
                'hours': cfg['tokenTtlHours'],
                'url': url,
            }
            try:
                title = (push_cfg.get('titleTemplate') or 'Still available? {name}').format(**ctx)
            except (KeyError, ValueError):
                title = f"Still available? {ctx['name']}"
            try:
                push_body = (push_cfg.get('bodyTemplate') or 'Tap to confirm {name} in {city}.').format(**ctx)
            except (KeyError, ValueError):
                push_body = f"Tap to confirm {ctx['name']}."
            try:
                push_result = notify_user(
                    owner,
                    title=title,
                    body=push_body,
                    url=url,
                    tag=f'heartbeat-{ping.id}',
                    ntype=NotificationType.HEARTBEAT,
                )
                push_ok = push_result.get('sent', 0) > 0
                if push_ok:
                    channels.append('push')
            except Exception:  # noqa: BLE001
                logger.exception('Heartbeat push failed owner=%s', owner.phone)

        skip_sms = push_ok and bool(push_cfg.get('preferPushOverSms'))
        if not skip_sms:
            try:
                send_sms(owner.phone, body)
                channels.append('sms')
                sms_used[owner_key] = sms_used.get(owner_key, 0) + 1
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    'Heartbeat SMS failed owner=%s ping=%s',
                    owner.phone,
                    ping.id,
                )
                if not push_ok:
                    ping.status = HeartbeatStatus.FAILED
                    ping.error_message = str(exc)[:500]
                    ping.save(update_fields=['status', 'error_message', 'updated_at'])
                    failed += 1
                    continue

        if not channels:
            ping.status = HeartbeatStatus.FAILED
            ping.error_message = ping.error_message or 'No push subscription and SMS did not send.'
            ping.save(update_fields=['status', 'error_message', 'updated_at'])
            failed += 1
            continue

        ping.status = HeartbeatStatus.SENT
        ping.sent_at = timezone.now()
        ping.channel = ','.join(channels)
        ping.error_message = ''
        ping.save(
            update_fields=['status', 'sent_at', 'channel', 'error_message', 'updated_at'],
        )
        sent += 1

    return {
        'skipped': False,
        'dryRun': not send,
        'envSmsEnabled': sms_kill_switch_on(),
        'adminSmsEnabled': bool(cfg.get('smsEnabled')),
        'candidates': len(candidates),
        'created': created,
        'sent': sent,
        'failed': failed,
        'capped': capped,
        'expired': expired,
    }


def heartbeat_stats() -> dict:
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    qs = HeartbeatPing.objects.filter(created_at__gte=week_ago)

    def _count(*statuses):
        return qs.filter(status__in=statuses).count()

    cfg = get_heartbeat_config()
    return {
        'windowDays': 7,
        'created': qs.count(),
        'sent': _count(
            HeartbeatStatus.SENT,
            HeartbeatStatus.CONFIRMED,
            HeartbeatStatus.MARKED_FULL,
        ),
        'dryRun': _count(HeartbeatStatus.DRY_RUN),
        'failed': _count(HeartbeatStatus.FAILED),
        'confirmed': _count(HeartbeatStatus.CONFIRMED),
        'markedFull': _count(HeartbeatStatus.MARKED_FULL),
        'pending': qs.filter(
            status__in=[HeartbeatStatus.PENDING, HeartbeatStatus.SENT],
            expires_at__gt=now,
        ).count(),
        'expired': _count(HeartbeatStatus.EXPIRED),
        'uniqueOwners': qs.values('owner_id').distinct().count(),
        'config': cfg,
        'envSmsEnabled': sms_kill_switch_on(),
        'liveSmsWouldSend': should_send_sms(cfg),
        'weekdayLabel': WEEKDAY_LABELS[int(cfg['weekday'])],
    }


def serialize_ping_public(ping: HeartbeatPing) -> dict:
    now = timezone.now()
    expired = ping.expires_at <= now and ping.status in (
        HeartbeatStatus.PENDING,
        HeartbeatStatus.SENT,
        HeartbeatStatus.DRY_RUN,
    )
    status = HeartbeatStatus.EXPIRED if expired else ping.status
    return {
        'token': ping.token,
        'targetType': ping.target_type,
        'targetId': str(ping.target_id),
        'name': ping.target_name,
        'city': ping.target_city,
        'status': status,
        'expiresAt': ping.expires_at.isoformat(),
        'respondedAt': ping.responded_at.isoformat() if ping.responded_at else None,
        'expired': expired or ping.status == HeartbeatStatus.EXPIRED,
        'alreadyResponded': ping.status
        in (HeartbeatStatus.CONFIRMED, HeartbeatStatus.MARKED_FULL),
    }


def respond_to_ping(ping: HeartbeatPing, action: str) -> HeartbeatPing:
    if ping.status in (HeartbeatStatus.CONFIRMED, HeartbeatStatus.MARKED_FULL):
        return ping
    if ping.expires_at <= timezone.now():
        ping.status = HeartbeatStatus.EXPIRED
        ping.save(update_fields=['status', 'updated_at'])
        raise ValueError('expired')

    obj = load_target(ping.target_type, ping.target_id)
    now = timezone.now()
    if action in ('available', 'confirm', 'yes', '1'):
        confirm_object(obj)
        ping.status = HeartbeatStatus.CONFIRMED
    elif action in ('full', 'unavailable', 'no', '2'):
        flag_unavailable(obj)
        ping.status = HeartbeatStatus.MARKED_FULL
    else:
        raise ValueError('invalid_action')
    ping.responded_at = now
    ping.save(update_fields=['status', 'responded_at', 'updated_at'])
    return ping
