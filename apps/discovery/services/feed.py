"""Unified public discover feed."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from discovery.services.freshness import is_fresh_enough
from hotels.models import Hotel
from hotels.serializers import HotelSerializer
from listings.models import ListingStatus, Property
from listings.serializers import PropertySerializer
from mess.models import Mess
from mess.serializers import MessSerializer


def _fresh_properties():
    qs = (
        Property.objects.filter(
            published=True,
            listing_status=ListingStatus.PUBLISHED,
            flagged_unavailable_at__isnull=True,
        )
        .select_related('owner')
        .prefetch_related('image_files')
    )
    return [p for p in qs if is_fresh_enough(p)]


def _fresh_hotels():
    qs = Hotel.objects.filter(
        is_deleted=False,
        flagged_unavailable_at__isnull=True,
    ).select_related('owner')
    return [h for h in qs if is_fresh_enough(h)]


def _fresh_messes():
    qs = Mess.objects.filter(
        is_deleted=False,
        flagged_unavailable_at__isnull=True,
    ).select_related('owner')
    return [m for m in qs if is_fresh_enough(m)]


def _sort_discovery(items, *, featured_attr='featured'):
    now = timezone.now()

    def key(obj):
        featured = bool(getattr(obj, featured_attr, False))
        until = getattr(obj, 'featured_until', None)
        if featured and until and until < now:
            featured = False
        confirmed = getattr(obj, 'last_confirmed_at', None) or getattr(
            obj,
            'updated_at',
            None,
        )
        rating = (
            getattr(obj, 'rating', None)
            or getattr(obj, 'average_rating', None)
            or 0
        )
        return (int(featured), confirmed or timezone.now(), rating)

    return sorted(items, key=key, reverse=True)


def build_feed(request, *, limit=8) -> dict:
    now = timezone.now()
    week = now - timedelta(days=7)
    properties = _sort_discovery(_fresh_properties())
    hotels = _sort_discovery(_fresh_hotels())
    messes = _sort_discovery(_fresh_messes())

    featured_props = [
        p
        for p in properties
        if p.featured and (not p.featured_until or p.featured_until >= now)
    ][:limit]
    open_messes = [m for m in messes if m.available_seats > 0][:limit]
    new_props = sorted(
        properties,
        key=lambda p: p.created_at,
        reverse=True,
    )[:limit]
    apartments = [p for p in properties if p.type == 'apartment'][:limit]

    ctx = {'request': request}
    return {
        'featured': PropertySerializer(featured_props, many=True, context=ctx).data,
        'listings': PropertySerializer(properties[:limit], many=True, context=ctx).data,
        'apartments': PropertySerializer(apartments, many=True, context=ctx).data,
        'hotels': HotelSerializer(hotels[:limit], many=True, context=ctx).data,
        'messes': MessSerializer(open_messes, many=True, context=ctx).data,
        'newThisWeek': PropertySerializer(
            [p for p in new_props if p.created_at >= week][:limit],
            many=True,
            context=ctx,
        ).data,
        'sponsoredLabel': 'Sponsored',
        'generatedAt': now.isoformat(),
    }


def unified_search(request) -> dict:
    """Filter all three verticals with shared city/area/query params."""
    params = request.query_params
    category = (params.get('category') or params.get('type') or 'all').lower()
    city = (params.get('city') or '').strip()
    area = (params.get('area') or '').strip()
    q = (params.get('q') or params.get('search') or '').strip()
    available_only = (params.get('availableOnly') or 'true').lower() in (
        '1',
        'true',
        'yes',
    )

    properties = _fresh_properties()
    hotels = _fresh_hotels()
    messes = _fresh_messes()

    if city:
        properties = [p for p in properties if p.city.lower() == city.lower()]
        hotels = [h for h in hotels if h.city.lower() == city.lower()]
        messes = [m for m in messes if m.city.lower() == city.lower()]
    if area:
        properties = [p for p in properties if p.area.lower() == area.lower()]
        hotels = [h for h in hotels if h.area.lower() == area.lower()]
    if q:
        ql = q.lower()
        properties = [
            p
            for p in properties
            if ql in p.name.lower() or ql in p.area.lower() or ql in p.city.lower()
        ]
        hotels = [
            h
            for h in hotels
            if ql in h.name.lower() or ql in h.area.lower() or ql in h.city.lower()
        ]
        messes = [
            m
            for m in messes
            if ql in m.name.lower() or ql in m.city.lower()
        ]
    if available_only:
        properties = [p for p in properties if p.available]
        hotels = [h for h in hotels if h.available_rooms > 0]
        messes = [m for m in messes if m.available_seats > 0]

    if category in ('apartment', 'mess', 'hostel', 'hotel') and category != 'hotel':
        if category != 'all':
            properties = [p for p in properties if p.type == category]

    ctx = {'request': request}
    include_props = category in ('all', 'apartment', 'mess', 'hostel')
    include_hotels = category in ('all', 'hotel')
    include_messes = category in ('all', 'mess')
    if category == 'hotel':
        include_props = False

    return {
        'category': category,
        'listings': PropertySerializer(
            _sort_discovery(properties) if include_props else [],
            many=True,
            context=ctx,
        ).data,
        'hotels': HotelSerializer(
            _sort_discovery(hotels) if include_hotels else [],
            many=True,
            context=ctx,
        ).data,
        'messes': MessSerializer(
            _sort_discovery(messes) if include_messes else [],
            many=True,
            context=ctx,
        ).data,
    }
