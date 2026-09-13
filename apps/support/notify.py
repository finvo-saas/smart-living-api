"""Complaint ticket alerts for the renter and owner.

In-app bell, browser push, and email when configured. Failures are logged
and never undo the ticket or reply.
"""
from __future__ import annotations

import logging

from django.db import transaction

from core.scope import ScopeType
from messaging.models import NotificationType

logger = logging.getLogger(__name__)

COMPLAINT_URL = '/complaints'

STATUS_LABEL = {
    'open': 'open',
    'in_progress': 'in progress',
    'resolved': 'resolved',
}


def schedule_complaint_created(complaint_id) -> None:
    transaction.on_commit(lambda cid=complaint_id: notify_complaint_created(cid))


def schedule_complaint_reply(complaint_id, author_id, body: str) -> None:
    text = (body or '').strip()
    transaction.on_commit(
        lambda cid=complaint_id, aid=author_id, excerpt=text: notify_complaint_reply(
            cid,
            aid,
            excerpt,
        ),
    )


def schedule_complaint_status(complaint_id, actor_id, status: str) -> None:
    transaction.on_commit(
        lambda cid=complaint_id, aid=actor_id, st=status: notify_complaint_status(
            cid,
            aid,
            st,
        ),
    )


def notify_complaint_created(complaint_id) -> None:
    complaint = _load(complaint_id)
    if complaint is None:
        return
    renter = complaint.user_name or 'A renter'
    place = _place(complaint)
    excerpt = _excerpt(complaint.description)
    body = f'{renter} opened a ticket about {place}: {complaint.title}.'
    if excerpt:
        body = f'{body} {excerpt}'
    _send(
        owner_users(complaint),
        title='New complaint ticket',
        body=body,
        tag=f'complaint-created-{complaint.id}',
    )


def notify_complaint_reply(complaint_id, author_id, body: str) -> None:
    complaint = _load(complaint_id)
    if complaint is None:
        return
    excerpt = _excerpt(body)
    title_bit = complaint.title
    if str(author_id) == str(complaint.user_id):
        who = complaint.user_name or 'The renter'
        text = f'{who} replied on "{title_bit}".'
        recipients = owner_users(complaint)
    else:
        who = _author_name(author_id) or 'The owner'
        text = f'{who} replied on your ticket "{title_bit}".'
        recipients = [complaint.user] if complaint.user_id else []
    if excerpt:
        text = f'{text} {excerpt}'
    _send(
        recipients,
        title='Complaint reply',
        body=text,
        tag=f'complaint-reply-{complaint.id}',
        skip_ids={author_id},
    )


def notify_complaint_status(complaint_id, actor_id, status: str) -> None:
    complaint = _load(complaint_id)
    if complaint is None:
        return
    label = STATUS_LABEL.get(status, status.replace('_', ' '))
    if str(actor_id) == str(complaint.user_id):
        who = complaint.user_name or 'The renter'
        text = f'{who} marked "{complaint.title}" as {label}.'
        recipients = owner_users(complaint)
    else:
        who = _author_name(actor_id) or 'The owner'
        text = f'{who} marked your ticket "{complaint.title}" as {label}.'
        recipients = [complaint.user] if complaint.user_id else []
    _send(
        recipients,
        title='Complaint updated',
        body=text,
        tag=f'complaint-status-{complaint.id}',
        skip_ids={actor_id},
    )


def owner_users(complaint):
    """Owners who should hear about this ticket, excluding the renter."""
    found = {}

    def add(user):
        if user is None or not getattr(user, 'id', None):
            return
        if complaint.user_id and user.id == complaint.user_id:
            return
        found[user.id] = user

    building = getattr(complaint, 'building', None)
    if building is not None:
        add(getattr(building, 'owner', None))

    if complaint.scope_type == ScopeType.MESS and complaint.scope_id:
        from mess.models import Mess

        mess = (
            Mess.objects.select_related('owner')
            .filter(pk=complaint.scope_id, is_deleted=False)
            .first()
        )
        if mess:
            add(mess.owner)
    elif complaint.scope_type == ScopeType.HOTEL and complaint.scope_id:
        from hotels.models import Hotel

        hotel = Hotel.objects.select_related('owner').filter(pk=complaint.scope_id).first()
        if hotel:
            add(hotel.owner)
    elif complaint.scope_type == ScopeType.BUILDING and complaint.scope_id and not found:
        from portfolio.models import Building

        extra = (
            Building.objects.select_related('owner')
            .filter(pk=complaint.scope_id)
            .first()
        )
        if extra:
            add(extra.owner)

    if not found and complaint.user_id:
        for user in _landlords_of(complaint.user_id):
            add(user)
    return list(found.values())


def _landlords_of(user_id):
    from hotels.models import HotelBooking
    from mess.models import MessStudent
    from portfolio.models import Tenancy, TenancyStatus

    tenancies = Tenancy.objects.filter(
        tenant_id=user_id,
        status=TenancyStatus.ACTIVE,
    ).select_related('flat__building__owner')
    for tenancy in tenancies:
        building = getattr(tenancy.flat, 'building', None)
        if building is not None:
            yield building.owner

    students = MessStudent.objects.filter(
        user_id=user_id,
        is_active=True,
        is_deleted=False,
    ).select_related('mess__owner')
    for student in students:
        if student.mess_id:
            yield student.mess.owner

    bookings = HotelBooking.objects.filter(
        user_id=user_id,
        is_deleted=False,
    ).select_related('hotel__owner')
    for booking in bookings:
        if booking.hotel_id:
            yield booking.hotel.owner


def _load(complaint_id):
    from support.models import Complaint

    return (
        Complaint.objects.filter(pk=complaint_id, is_deleted=False)
        .select_related('user', 'building__owner')
        .first()
    )


def _send(users, *, title: str, body: str, tag: str, skip_ids=None) -> None:
    from accounts.services.email import notify_channels

    skip = {str(item) for item in (skip_ids or set()) if item}
    seen = set()
    for user in users:
        if user is None or not getattr(user, 'id', None):
            continue
        if str(user.id) in skip or user.id in seen:
            continue
        seen.add(user.id)
        try:
            notify_channels(
                user,
                title=title[:255],
                body=body,
                url=COMPLAINT_URL,
                ntype=NotificationType.COMPLAINT,
                tag=tag,
            )
        except Exception:
            logger.exception(
                'Complaint notice failed tag=%s user=%s',
                tag,
                user.id,
            )


def _author_name(user_id) -> str:
    if not user_id:
        return ''
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id).only('name', 'phone').first()
    if user is None:
        return ''
    return user.name or (f'User {user.phone[-4:]}' if user.phone else '')


def _place(complaint) -> str:
    bits = [complaint.scope_name or '']
    if complaint.target_label:
        bits.append(complaint.target_label)
    text = ' · '.join(bit for bit in bits if bit)
    return text or 'your property'


def _excerpt(content: str, limit: int = 140) -> str:
    text = ' '.join((content or '').split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + '…'
