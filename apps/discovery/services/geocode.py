"""Address → coordinates via Nominatim (default) or Mapbox / Google."""
from __future__ import annotations

import hashlib
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('discovery.geocode')


def geocode_address(
    address: str,
    *,
    city: str = '',
    area: str = '',
) -> dict[str, Any] | None:
    """
    Return {'lat': float, 'lng': float, 'displayName': str, 'provider': str} or None.
    """
    query_parts = [p for p in (address, area, city, 'Bangladesh') if p]
    query = ', '.join(query_parts).strip()
    if len(query) < 5:
        return None

    # Memcached forbids spaces/commas/control chars in keys — hash the query.
    digest = hashlib.sha256(query.lower().encode('utf-8')).hexdigest()[:32]
    cache_key = f'geocode:v1:{digest}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    provider = (getattr(settings, 'GEOCODER_PROVIDER', 'nominatim') or 'nominatim').lower()
    result = None
    if provider == 'mapbox':
        result = _geocode_mapbox(query)
    elif provider in ('google', 'google_maps'):
        result = _geocode_google(query)
    else:
        result = _geocode_nominatim(query)

    if result:
        cache.set(cache_key, result, timeout=60 * 60 * 24 * 30)
    return result


def ensure_property_coordinates(prop) -> bool:
    """Fill lat/lng on property when missing. Returns True if updated."""
    if prop.latitude is not None and prop.longitude is not None:
        return False
    hit = geocode_address(prop.address or '', city=prop.city or '', area=prop.area or '')
    if not hit:
        return False
    prop.latitude = hit['lat']
    prop.longitude = hit['lng']
    prop.save(update_fields=['latitude', 'longitude', 'updated_at'])
    return True


def _geocode_nominatim(query: str) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            'q': query,
            'format': 'json',
            'limit': 1,
            'countrycodes': 'bd',
        },
    )
    email = getattr(settings, 'GEOCODER_CONTACT_EMAIL', '') or 'support@smartbasa.local'
    req = urllib.request.Request(
        f'https://nominatim.openstreetmap.org/search?{params}',
        headers={
            'User-Agent': f'SmartBasa/1.0 ({email})',
            'Accept': 'application/json',
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning('Nominatim geocode failed: %s', exc)
        return None
    if not rows:
        return None
    row = rows[0]
    try:
        return {
            'lat': float(row['lat']),
            'lng': float(row['lon']),
            'displayName': row.get('display_name') or query,
            'provider': 'nominatim',
        }
    except (KeyError, TypeError, ValueError):
        return None


def _geocode_mapbox(query: str) -> dict[str, Any] | None:
    token = (getattr(settings, 'MAPBOX_ACCESS_TOKEN', '') or '').strip()
    if not token:
        return _geocode_nominatim(query)
    encoded = urllib.parse.quote(query)
    url = (
        f'https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded}.json'
        f'?access_token={token}&country=BD&limit=1'
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        features = payload.get('features') or []
        if not features:
            return None
        lng, lat = features[0]['center']
        return {
            'lat': float(lat),
            'lng': float(lng),
            'displayName': features[0].get('place_name') or query,
            'provider': 'mapbox',
        }
    except (urllib.error.URLError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning('Mapbox geocode failed: %s', exc)
        return _geocode_nominatim(query)


def _geocode_google(query: str) -> dict[str, Any] | None:
    key = (getattr(settings, 'GOOGLE_MAPS_API_KEY', '') or '').strip()
    if not key:
        return _geocode_nominatim(query)
    params = urllib.parse.urlencode(
        {'address': query, 'key': key, 'region': 'bd', 'components': 'country:BD'},
    )
    try:
        with urllib.request.urlopen(
            f'https://maps.googleapis.com/maps/api/geocode/json?{params}',
            timeout=10,
        ) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        results = payload.get('results') or []
        if not results:
            return None
        loc = results[0]['geometry']['location']
        return {
            'lat': float(loc['lat']),
            'lng': float(loc['lng']),
            'displayName': results[0].get('formatted_address') or query,
            'provider': 'google',
        }
    except (urllib.error.URLError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning('Google geocode failed: %s', exc)
        return _geocode_nominatim(query)
