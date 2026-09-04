"""Notify users when new listings match their saved searches."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from discovery.models import SavedSearch
from listings.models import ListingStatus, Property
from messaging.services.push import create_in_app_notification, send_web_push


def run_saved_search_notifications(lookback_hours: int = 6) -> dict:
    since = timezone.now() - timedelta(hours=lookback_hours)
    searches = (
        SavedSearch.objects.filter(is_active=True)
        .select_related('user')
        .order_by('last_checked')[:200]
    )
    notified = 0
    matched = 0
    for search in searches:
        props = _matching_properties(search.filters or {}, since)
        count = props.count()
        search.match_count = count
        search.last_checked = timezone.now()
        search.save(update_fields=['match_count', 'last_checked', 'updated_at'])
        if count <= 0:
            continue
        matched += count
        top = props.first()
        title = f'{count} new match{"es" if count != 1 else ""} for “{search.name}”'
        body = (
            f'{top.name} in {top.area}, {top.city} — ৳{int(top.rent):,}/mo'
            if top
            else f'{count} listings match your saved search.'
        )
        url = f'/search?saved={search.id}'
        create_in_app_notification(
            search.user,
            title=title,
            body=body,
            url=url,
            ntype='saved_search',
        )
        send_web_push(search.user, title=title, body=body, url=url, tag=f'saved-{search.id}')
        try:
            from accounts.services.email import send_email

            email = getattr(search.user, 'email', '') or ''
            if email:
                send_email(email, title, f'{body}\n\nOpen: {url}')
        except Exception:
            pass
        notified += 1
    return {'searches': len(searches), 'notified': notified, 'matches': matched}


def _matching_properties(filters: dict, since):
    qs = Property.objects.filter(
        published=True,
        listing_status=ListingStatus.PUBLISHED,
        flagged_unavailable_at__isnull=True,
        created_at__gte=since,
    )
    city = filters.get('city')
    area = filters.get('area')
    ptype = filters.get('propertyType') or filters.get('type')
    gender = filters.get('gender')
    verified_only = filters.get('verifiedOnly')
    rent_min = filters.get('rentMin') or (filters.get('rentRange') or [None, None])[0]
    rent_max = filters.get('rentMax') or (filters.get('rentRange') or [None, None])[1]
    q = filters.get('q') or filters.get('search') or filters.get('searchQuery')

    if city and city != 'all':
        qs = qs.filter(city__iexact=str(city).strip())
    if area:
        qs = qs.filter(area__iexact=str(area).strip())
    if ptype and ptype != 'all':
        qs = qs.filter(type=ptype)
    if gender and gender != 'all':
        qs = qs.filter(gender__in=[gender, 'mixed'])
    if verified_only:
        qs = qs.filter(Q(verified=True) | Q(verification_status='verified'))
    if rent_min is not None:
        try:
            qs = qs.filter(rent__gte=float(rent_min))
        except (TypeError, ValueError):
            pass
    if rent_max is not None:
        try:
            qs = qs.filter(rent__lte=float(rent_max))
        except (TypeError, ValueError):
            pass
    if q:
        qs = (
            qs.filter(name__icontains=q)
            | qs.filter(area__icontains=q)
            | qs.filter(city__icontains=q)
        )
    return qs.order_by('-created_at')
