"""Heartbeat / freshness helpers for public discovery."""

from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone

STALE_HOURS = 24 * 7
HIDE_AFTER_DAYS = 30


def confirm_object(obj) -> None:
    now = timezone.now()
    obj.last_confirmed_at = now
    obj.flagged_unavailable_at = None
    fields = ['last_confirmed_at', 'flagged_unavailable_at', 'updated_at']
    if hasattr(obj, 'available'):
        obj.available = True
        fields.append('available')
    obj.save(update_fields=fields)


def flag_unavailable(obj) -> None:
    obj.flagged_unavailable_at = timezone.now()
    fields = ['flagged_unavailable_at', 'updated_at']
    if hasattr(obj, 'available'):
        obj.available = False
        fields.append('available')
    obj.save(update_fields=fields)


def freshness_dict(obj) -> dict:
    ts = getattr(obj, 'last_confirmed_at', None) or getattr(obj, 'updated_at', None)
    hours = None
    if ts:
        hours = max(0, int((timezone.now() - ts).total_seconds() // 3600))
    flagged = bool(getattr(obj, 'flagged_unavailable_at', None))
    return {
        'lastConfirmedAt': ts.isoformat() if ts else None,
        'confirmedHoursAgo': hours,
        'stale': bool(hours is not None and hours >= STALE_HOURS),
        'flaggedUnavailable': flagged,
    }


def is_fresh_enough(obj) -> bool:
    if getattr(obj, 'flagged_unavailable_at', None):
        return False
    ts = getattr(obj, 'last_confirmed_at', None) or getattr(obj, 'created_at', None)
    if ts is None:
        return True
    return ts >= timezone.now() - timedelta(days=HIDE_AFTER_DAYS)


def expire_featured() -> int:
    now = timezone.now()
    from listings.models import Property
    from hotels.models import Hotel
    from mess.models import Mess

    count = 0
    count += Property.objects.filter(
        featured=True,
        featured_until__isnull=False,
        featured_until__lt=now,
    ).update(featured=False)
    count += Hotel.objects.filter(
        featured=True,
        featured_until__isnull=False,
        featured_until__lt=now,
    ).update(featured=False)
    count += Mess.objects.filter(
        featured=True,
        featured_until__isnull=False,
        featured_until__lt=now,
    ).update(featured=False)
    return count


def auto_dim_stale() -> dict:
    """Unpublish listings not confirmed in HIDE_AFTER_DAYS; flag hotels/messes."""
    from hotels.models import Hotel
    from listings.models import ListingStatus, Property
    from mess.models import Mess

    cutoff = timezone.now() - timedelta(days=HIDE_AFTER_DAYS)

    stale_props = Property.objects.filter(
        published=True,
        listing_status=ListingStatus.PUBLISHED,
    ).filter(
        models.Q(last_confirmed_at__isnull=True, created_at__lt=cutoff)
        | models.Q(last_confirmed_at__lt=cutoff),
    )
    prop_count = stale_props.update(
        published=False,
        listing_status=ListingStatus.PAUSED,
    )

    stale_hotels = Hotel.objects.filter(
        is_deleted=False,
        flagged_unavailable_at__isnull=True,
    ).filter(
        models.Q(last_confirmed_at__isnull=True, created_at__lt=cutoff)
        | models.Q(last_confirmed_at__lt=cutoff),
    )
    hotel_count = stale_hotels.update(flagged_unavailable_at=timezone.now())

    stale_messes = Mess.objects.filter(
        is_deleted=False,
        flagged_unavailable_at__isnull=True,
    ).filter(
        models.Q(last_confirmed_at__isnull=True, created_at__lt=cutoff)
        | models.Q(last_confirmed_at__lt=cutoff),
    )
    mess_count = stale_messes.update(flagged_unavailable_at=timezone.now())

    return {
        'cutoffDays': HIDE_AFTER_DAYS,
        'dimmedProperties': prop_count,
        'dimmedHotels': hotel_count,
        'dimmedMesses': mess_count,
    }
