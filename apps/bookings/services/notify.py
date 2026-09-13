"""Booking alerts for the renter and owner.

Uses the shared notify path: in-app bell, browser push, and email when configured.
Failures are logged and never undo the booking.
"""
from __future__ import annotations

import logging

from django.db import transaction

from messaging.models import NotificationType

logger = logging.getLogger(__name__)

OWNER_URL = '/my-properties/bookings'
RENTER_URL = '/my-bookings'


def _owner_url(booking) -> str:
    if booking.property_type in ('mess', 'hostel'):
        return '/my-properties/bookings?scope=mess'
    return OWNER_URL
KIND = {
    'apartment': 'flat',
    'mess': 'mess',
    'hostel': 'hostel',
    'hotel': 'hotel',
}


def schedule_booking_notice(booking_id, event: str, reason: str = '') -> None:
    """Send after the booking transaction commits."""
    transaction.on_commit(
        lambda: send_booking_notice(booking_id, event, reason),
    )


def send_booking_notice(booking_id, event: str, reason: str = '') -> None:
    from accounts.services.email import notify_channels
    from bookings.models import PropertyBooking

    try:
        booking = PropertyBooking.objects.select_related('renter', 'owner').get(
            pk=booking_id,
            is_deleted=False,
        )
    except PropertyBooking.DoesNotExist:
        return

    kind = KIND.get(booking.property_type, 'listing')
    place = booking.property_name or kind
    renter = booking.renter_name or 'A renter'
    owner = booking.owner_name or 'The owner'
    reason = (reason or '').strip()

    notices = []
    if event == 'requested':
        notices.append(
            (
                booking.owner,
                f'New {kind} request',
                f'{renter} requested {place}. Review it in bookings.',
                _owner_url(booking),
            )
        )
        notices.append(
            (
                booking.renter,
                'Request sent',
                f'Your request for {place} was sent to the owner.',
                RENTER_URL,
            )
        )
    elif event == 'accepted':
        notices.append(
            (
                booking.renter,
                f'{kind.capitalize()} request accepted',
                f'{owner} accepted your request for {place}.',
                RENTER_URL,
            )
        )
    elif event == 'instant':
        notices.append(
            (
                booking.owner,
                f'New {kind} booking',
                f'{renter} booked {place}. It was confirmed instantly.',
                _owner_url(booking),
            )
        )
        notices.append(
            (
                booking.renter,
                'Booking confirmed',
                f'Your booking for {place} is confirmed.',
                RENTER_URL,
            )
        )
    elif event == 'rejected':
        body = f'{owner} declined your request for {place}.'
        if reason:
            body = f'{body} Reason: {reason}'
        notices.append(
            (
                booking.renter,
                f'{kind.capitalize()} request declined',
                body,
                RENTER_URL,
            )
        )
    else:
        return

    for user, title, body, url in notices:
        if user is None:
            continue
        try:
            notify_channels(
                user,
                title=title,
                body=body,
                url=url,
                ntype=NotificationType.SYSTEM,
                tag=f'booking-{event}',
            )
        except Exception:
            logger.exception(
                'Booking notice failed booking=%s event=%s user=%s',
                booking_id,
                event,
                getattr(user, 'id', None),
            )
