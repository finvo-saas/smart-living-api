"""Tell active renters when an owner publishes a notice."""
from __future__ import annotations

import logging
import re

from django.contrib.auth import get_user_model
from django.db import transaction

from core.scope import ScopeType
from messaging.models import NotificationType

logger = logging.getLogger(__name__)

NOTICE_URL = '/notices'


def schedule_notice_published(notice) -> None:
    notice_id = notice.id
    transaction.on_commit(lambda: notify_notice_published(notice_id))


def notify_notice_published(notice_id) -> None:
    from accounts.services.email import notify_channels
    from ops.models import Notice

    notice = Notice.objects.filter(pk=notice_id, is_deleted=False).first()
    if notice is None:
        return

    place = notice.scope_name or 'your place'
    excerpt = _excerpt(notice.content)
    body = f'{place}: {excerpt}' if excerpt else f'A new notice was posted for {place}.'
    title = f'New notice: {notice.title}'

    for user in recipient_users(notice):
        try:
            notify_channels(
                user,
                title=title[:255],
                body=body,
                url=NOTICE_URL,
                ntype=NotificationType.SYSTEM,
                tag=f'notice-{notice.id}',
            )
        except Exception:
            logger.exception(
                'Notice notify failed notice=%s user=%s',
                notice_id,
                getattr(user, 'id', None),
            )


def recipient_users(notice):
    """Active renters for this notice, excluding the owner who posted it."""
    users = {}
    for user in _scope_users(notice):
        if user is None or user.id in users:
            continue
        if notice.created_by_id and user.id == notice.created_by_id:
            continue
        users[user.id] = user
    return list(users.values())


def _scope_users(notice):
    if notice.scope_type == ScopeType.MESS:
        yield from _mess_users(notice.scope_id)
    elif notice.scope_type == ScopeType.BUILDING:
        yield from _building_users(notice.scope_id, notice.target_ids or [])
    elif notice.scope_type == ScopeType.HOTEL:
        yield from _hotel_users(notice.scope_id)


def _mess_users(mess_id):
    from bookings.models import BookingStatus, PropertyBooking
    from mess.models import MessStudent

    students = MessStudent.objects.filter(
        mess_id=mess_id,
        is_active=True,
        is_deleted=False,
    ).select_related('user')
    unmatched_phones = []
    for student in students:
        if student.user_id:
            yield student.user
        elif student.phone:
            unmatched_phones.append(student.phone)
    yield from _users_by_phones(unmatched_phones)

    listing_ids = (
        PropertyBooking.objects.filter(
            property__linked_messes__id=mess_id,
            status=BookingStatus.APPROVED,
            is_deleted=False,
        )
        .values_list('renter_id', flat=True)
    )
    User = get_user_model()
    yield from User.objects.filter(id__in=listing_ids)


def _building_users(building_id, target_ids):
    from portfolio.models import Tenancy, TenancyStatus

    qs = Tenancy.objects.filter(
        flat__building_id=building_id,
        status=TenancyStatus.ACTIVE,
        tenant__isnull=False,
    ).select_related('tenant')
    targets = {str(item) for item in target_ids if item}
    if targets:
        qs = qs.filter(flat_id__in=targets)
    for tenancy in qs:
        yield tenancy.tenant


def _hotel_users(hotel_id):
    from hotels.models import HotelBooking, HotelBookingStatus

    bookings = HotelBooking.objects.filter(
        hotel_id=hotel_id,
        status__in=(
            HotelBookingStatus.CONFIRMED,
            HotelBookingStatus.CHECKED_IN,
        ),
    ).select_related('user')
    for booking in bookings:
        yield booking.user


def _users_by_phones(phones):
    if not phones:
        return
    User = get_user_model()
    wanted = set()
    for phone in phones:
        wanted.update(_phone_keys(phone))
    if not wanted:
        return
    for user in User.objects.exclude(phone=''):
        if _phone_keys(user.phone) & wanted:
            yield user


def _phone_keys(value: str) -> set[str]:
    digits = re.sub(r'\D', '', value or '')
    if len(digits) < 10:
        return set()
    keys = {digits[-11:] if len(digits) >= 11 else digits, digits[-10:]}
    return {key for key in keys if key}


def _excerpt(content: str, limit: int = 160) -> str:
    text = ' '.join((content or '').split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + '…'
