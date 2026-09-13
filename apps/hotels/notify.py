"""Hotel booking alerts for the guest and the owner."""
from __future__ import annotations

import logging

from django.db import transaction

from messaging.models import NotificationType

logger = logging.getLogger(__name__)


def schedule_hotel_booking(booking_id, event: str, reason: str = '', actor_id=None) -> None:
    transaction.on_commit(
        lambda bid=booking_id, ev=event, why=reason, aid=actor_id: notify_hotel_booking(
            bid,
            ev,
            why,
            actor_id=aid,
        ),
    )


def notify_hotel_booking(booking_id, event: str, reason: str = '', actor_id=None) -> None:
    from hotels.models import HotelBooking

    booking = (
        HotelBooking.objects.filter(pk=booking_id, is_deleted=False)
        .select_related('hotel', 'hotel__owner', 'user', 'room')
        .first()
    )
    if booking is None or booking.hotel_id is None:
        return

    hotel = booking.hotel
    guest = booking.guest_name or (booking.user.name if booking.user_id else 'A guest')
    place = hotel.name or 'your hotel'
    dates = f'{booking.check_in.isoformat()} – {booking.check_out.isoformat()}'
    owner_url = f'/my-hotels/{hotel.id}/bookings'
    guest_url = f'/hotels/{hotel.id}'
    notices = []

    if event == 'requested':
        notices.append((
            hotel.owner,
            'New hotel booking',
            f'{guest} requested {place} ({dates}).',
            owner_url,
        ))
        notices.append((
            booking.user,
            'Booking request sent',
            f'Your request for {place} ({dates}) was sent to the hotel.',
            guest_url,
        ))
    elif event == 'confirmed':
        notices.append((
            hotel.owner,
            'Hotel booking confirmed',
            f'{guest} is confirmed at {place} ({dates}).',
            owner_url,
        ))
        notices.append((
            booking.user,
            'Hotel booking confirmed',
            f'{place} confirmed your stay ({dates}).',
            guest_url,
        ))
    elif event == 'checked-in':
        notices.append((
            booking.user,
            'Checked in',
            f'You are checked in at {place}.',
            guest_url,
        ))
    elif event == 'checked-out':
        notices.append((
            booking.user,
            'Checked out',
            f'You are checked out of {place}.',
            guest_url,
        ))
        notices.append((
            hotel.owner,
            'Guest checked out',
            f'{guest} checked out of {place}.',
            owner_url,
        ))
    elif event == 'cancelled':
        why = (reason or '').strip()
        guest_body = f'Your booking at {place} ({dates}) was cancelled.'
        owner_body = f'{guest} cancelled their stay at {place} ({dates}).'
        if why:
            guest_body = f'{guest_body} Reason: {why}'
            owner_body = f'{owner_body} Reason: {why}'
        notices.append((booking.user, 'Hotel booking cancelled', guest_body, guest_url))
        notices.append((hotel.owner, 'Hotel booking cancelled', owner_body, owner_url))
    else:
        return

    if actor_id:
        notices = [row for row in notices if getattr(row[0], 'id', None) != actor_id]
    _fanout(notices, tag=f'hotel-{event}-{booking.id}')


def _fanout(notices, *, tag: str) -> None:
    from accounts.services.email import notify_channels

    seen = set()
    for user, title, body, url in notices:
        if user is None or not getattr(user, 'id', None) or user.id in seen:
            continue
        seen.add(user.id)
        try:
            notify_channels(
                user,
                title=title[:255],
                body=body,
                url=url,
                ntype=NotificationType.SYSTEM,
                tag=tag,
            )
        except Exception:
            logger.exception('Hotel notice failed tag=%s user=%s', tag, user.id)
