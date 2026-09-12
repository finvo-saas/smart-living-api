"""Address → coordinates via Nominatim (default) or Mapbox / Google."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger('discovery.geocode')

_HOUSE_FRAGMENT = re.compile(
    r'^(house|holding|road|rd|block|plot|flat|floor|lane|sector)[\s.\-]*([a-z]|\d)',
    re.IGNORECASE,
)
# "Road 12 Block C" exists in several Dhaka areas. If the address also names a
# neighborhood, a street hit farther than this from that neighborhood is rejected.
_STREET_DRIFT_KM = 1.5


def geocode_address(
    address: str,
    *,
    city: str = '',
    area: str = '',
) -> dict[str, Any] | None:
    """
    Return {'lat': float, 'lng': float, 'displayName': str, 'provider': str} or None.

    A house line like "Road-12, Block-C" is mapped in more than one Dhaka area.
    When the address also names a neighborhood, that neighborhood wins if the
    street match is far away.
    """
    city = (city or '').strip()
    area = (area or '').strip()
    if area.lower() == city.lower():
        area = ''

    street_query = _join(address, area, city, 'Bangladesh')
    place_query = _place_query(address, city)
    if place_query == street_query:
        place_query = ''

    street_hit = _lookup(street_query) if len(street_query) >= 5 else None
    place_hit = None
    if place_query and len(place_query) >= 5:
        if street_hit is not None:
            time.sleep(1.1)
        place_hit = _lookup(place_query)

    if place_hit and street_hit:
        if _distance_km(place_hit, street_hit) > _STREET_DRIFT_KM:
            return place_hit
        return street_hit
    return street_hit or place_hit


def ensure_property_coordinates(prop) -> bool:
    """Fill lat/lng on property when missing. Returns True if updated."""
    if prop.latitude is not None and prop.longitude is not None:
        return False
    return refresh_property_coordinates(prop)


def refresh_property_coordinates(prop) -> bool:
    """Re-resolve lat/lng from the current address. Returns True if the pin moved."""
    hit = geocode_address(
        prop.address or '',
        city=prop.city or '',
        area=prop.area or '',
    )
    if not hit:
        return False
    if (
        prop.latitude is not None
        and prop.longitude is not None
        and abs(float(prop.latitude) - hit['lat']) < 0.00001
        and abs(float(prop.longitude) - hit['lng']) < 0.00001
    ):
        return False
    prop.latitude = hit['lat']
    prop.longitude = hit['lng']
    prop.save(update_fields=['latitude', 'longitude', 'updated_at'])
    return True


def _place_query(address: str, city: str) -> str:
    parts = [part.strip() for part in re.split(r'[,|\n]', address or '') if part.strip()]
    places = [part for part in parts if not _HOUSE_FRAGMENT.match(part)]
    if not places:
        return ''
    return _join(*places, city, 'Bangladesh')


def _join(*parts: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        text = (part or '').strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return ', '.join(out)


def _lookup(query: str) -> dict[str, Any] | None:
    digest = hashlib.sha256(query.lower().encode('utf-8')).hexdigest()[:32]
    cache_key = f'geocode:v2:{digest}'
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


def _distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    r = 6371
    p1, p2 = math.radians(a['lat']), math.radians(b['lat'])
    dphi = math.radians(b['lat'] - a['lat'])
    dl = math.radians(b['lng'] - a['lng'])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


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
