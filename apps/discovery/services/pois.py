"""Nearby POIs via OpenStreetMap Overpass (no Google Places billing)."""
from __future__ import annotations

import json
import logging
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger('discovery.pois')

OVERPASS_ENDPOINTS = (
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter',
)

# Successful non-empty payloads only. Never long-cache empty (Overpass flakes).
CACHE_TTL_OK = 3600
CACHE_TTL_EMPTY = 15
_cache: dict[str, tuple[float, dict]] = {}
_inflight: dict[str, threading.Event] = {}
_lock = threading.Lock()

CATEGORY_RULES = (
    ('hospital', ('hospital', 'clinic', 'doctors')),
    ('school', ('school', 'university', 'college')),
    ('market', ('marketplace', 'supermarket', 'convenience', 'mall')),
    ('mosque', ('place_of_worship', 'mosque')),
    ('bus', ('bus_stop', 'bus_station')),
    ('metro', ('station', 'subway_entrance', 'subway')),
)


def nearby_pois(lat: float, lng: float, radius: int = 1500) -> dict:
    radius = max(300, min(int(radius), 3000))
    # v3: singleflight + short empty TTL (avoids Strict Mode double-fetch 429)
    key = f'v3:{round(lat, 4)}:{round(lng, 4)}:{radius}'
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < (
        CACHE_TTL_OK if _has_pois(hit[1]) else CACHE_TTL_EMPTY
    ):
        return hit[1]

    # Coalesce concurrent requests for the same pin (dev Strict Mode / parallel tabs)
    leader = False
    event: threading.Event
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < (
            CACHE_TTL_OK if _has_pois(hit[1]) else CACHE_TTL_EMPTY
        ):
            return hit[1]
        if key in _inflight:
            event = _inflight[key]
        else:
            event = threading.Event()
            _inflight[key] = event
            leader = True

    if not leader:
        event.wait(timeout=35)
        with _lock:
            hit = _cache.get(key)
            if hit:
                return hit[1]
        return _empty_payload(lat, lng, radius)

    try:
        payload = _fetch_and_group(lat, lng, radius)
        with _lock:
            _cache[key] = (time.time(), payload)
        return payload
    finally:
        with _lock:
            event = _inflight.pop(key, None)
        if event is not None:
            event.set()


def _empty_payload(lat: float, lng: float, radius: int) -> dict:
    return {
        'lat': lat,
        'lng': lng,
        'radius': radius,
        'pois': {name: [] for name, _ in CATEGORY_RULES},
        'source': 'openstreetmap',
    }


def _fetch_and_group(lat: float, lng: float, radius: int) -> dict:
    elements = _query_overpass(lat, lng, radius)
    grouped: dict[str, list] = {name: [] for name, _ in CATEGORY_RULES}
    for el in elements:
        tags = el.get('tags') or {}
        el_lat = el.get('lat')
        el_lng = el.get('lon')
        if el_lat is None or el_lng is None:
            center = el.get('center') or {}
            el_lat = center.get('lat')
            el_lng = center.get('lon')
        if el_lat is None or el_lng is None:
            continue
        category = _classify(tags)
        if not category or len(grouped[category]) >= 8:
            continue
        name = (
            tags.get('name')
            or tags.get('name:en')
            or tags.get('name:bn')
            or category.title()
        )
        grouped[category].append({
            'name': name,
            'lat': float(el_lat),
            'lng': float(el_lng),
            'distanceM': round(_haversine(lat, lng, float(el_lat), float(el_lng))),
            'category': category,
        })

    for items in grouped.values():
        items.sort(key=lambda x: x['distanceM'])

    return {
        'lat': lat,
        'lng': lng,
        'radius': radius,
        'pois': grouped,
        'source': 'openstreetmap',
    }


def _has_pois(payload: dict) -> bool:
    pois = payload.get('pois') or {}
    return any(pois.get(k) for k, _ in CATEGORY_RULES)


def _classify(tags: dict) -> str | None:
    amenity = (tags.get('amenity') or '').lower()
    shop = (tags.get('shop') or '').lower()
    highway = (tags.get('highway') or '').lower()
    railway = (tags.get('railway') or '').lower()
    station = (tags.get('station') or '').lower()
    religion = (tags.get('religion') or '').lower()
    blob = {amenity, shop, highway, railway, station}

    if amenity == 'place_of_worship' and religion in ('muslim', 'islam'):
        return 'mosque'
    if amenity == 'place_of_worship' and 'mosque' in (tags.get('name') or '').lower():
        return 'mosque'
    if railway in ('station', 'subway_entrance') or station == 'subway':
        return 'metro'
    if highway == 'bus_stop' or amenity == 'bus_station':
        return 'bus'
    if amenity in ('hospital', 'clinic', 'doctors'):
        return 'hospital'
    if amenity in ('school', 'university', 'college'):
        return 'school'
    if amenity == 'marketplace' or shop in ('supermarket', 'convenience', 'mall'):
        return 'market'
    if amenity == 'place_of_worship':
        return 'mosque'
    for category, keys in CATEGORY_RULES:
        if blob & set(keys):
            return category
    return None


def _query_overpass(lat: float, lng: float, radius: int) -> list:
    # Include ways (many BD hospitals/mosques are mapped as areas, not nodes).
    query = f"""
[out:json][timeout:25];
(
  nwr["amenity"="hospital"](around:{radius},{lat},{lng});
  nwr["amenity"="clinic"](around:{radius},{lat},{lng});
  nwr["amenity"="doctors"](around:{radius},{lat},{lng});
  nwr["amenity"="school"](around:{radius},{lat},{lng});
  nwr["amenity"="university"](around:{radius},{lat},{lng});
  nwr["amenity"="college"](around:{radius},{lat},{lng});
  nwr["amenity"="marketplace"](around:{radius},{lat},{lng});
  nwr["shop"="supermarket"](around:{radius},{lat},{lng});
  nwr["shop"="convenience"](around:{radius},{lat},{lng});
  nwr["amenity"="place_of_worship"](around:{radius},{lat},{lng});
  nwr["highway"="bus_stop"](around:{radius},{lat},{lng});
  nwr["amenity"="bus_station"](around:{radius},{lat},{lng});
  nwr["railway"="station"](around:{radius},{lat},{lng});
  nwr["railway"="subway_entrance"](around:{radius},{lat},{lng});
  nwr["public_transport"="station"](around:{radius},{lat},{lng});
);
out center tags 120;
"""
    body = urllib.parse.urlencode({'data': query}).encode('utf-8')
    last_error = None
    for url in OVERPASS_ENDPOINTS:
        for attempt in range(2):
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    'User-Agent': (
                        'SmartBasa/1.0 (poi-overlay; contact=support@smartbasa.com)'
                    ),
                },
                method='POST',
            )
            try:
                with urllib.request.urlopen(req, timeout=28) as resp:
                    payload = json.loads(resp.read().decode('utf-8'))
                elements = payload.get('elements') or []
                if elements:
                    return elements
                logger.info('Overpass empty at %s for %s,%s', url, lat, lng)
                break
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429 and attempt == 0:
                    time.sleep(1.5)
                    continue
                logger.warning('Overpass HTTP %s at %s', exc.code, url)
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                last_error = exc
                logger.warning('Overpass failed at %s: %s', url, exc)
                break
        time.sleep(0.4)
    if last_error:
        logger.warning('All Overpass endpoints failed: %s', last_error)
    return []


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
