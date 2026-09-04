"""Nearby POIs via OpenStreetMap Overpass (no Google Places billing)."""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

OVERPASS_ENDPOINTS = (
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
)

CACHE_TTL = 3600
_cache: dict[str, tuple[float, dict]] = {}

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
    key = f'{round(lat, 3)}:{round(lng, 3)}:{radius}'
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]

    elements = _query_overpass(lat, lng, radius)
    grouped: dict[str, list] = {name: [] for name, _ in CATEGORY_RULES}
    for el in elements:
        tags = el.get('tags') or {}
        el_lat = el.get('lat')
        el_lng = el.get('lon')
        if el_lat is None or el_lng is None:
            continue
        category = _classify(tags)
        if not category or len(grouped[category]) >= 8:
            continue
        name = tags.get('name') or tags.get('name:en') or tags.get('name:bn') or category.title()
        grouped[category].append({
            'name': name,
            'lat': el_lat,
            'lng': el_lng,
            'distanceM': round(_haversine(lat, lng, el_lat, el_lng)),
            'category': category,
        })

    for items in grouped.values():
        items.sort(key=lambda x: x['distanceM'])

    payload = {
        'lat': lat,
        'lng': lng,
        'radius': radius,
        'pois': grouped,
        'source': 'openstreetmap',
    }
    _cache[key] = (now, payload)
    return payload


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
    query = f"""
[out:json][timeout:8];
(
  node["amenity"="hospital"](around:{radius},{lat},{lng});
  node["amenity"="clinic"](around:{radius},{lat},{lng});
  node["amenity"="school"](around:{radius},{lat},{lng});
  node["amenity"="university"](around:{radius},{lat},{lng});
  node["amenity"="college"](around:{radius},{lat},{lng});
  node["amenity"="marketplace"](around:{radius},{lat},{lng});
  node["shop"="supermarket"](around:{radius},{lat},{lng});
  node["shop"="convenience"](around:{radius},{lat},{lng});
  node["amenity"="place_of_worship"](around:{radius},{lat},{lng});
  node["highway"="bus_stop"](around:{radius},{lat},{lng});
  node["amenity"="bus_station"](around:{radius},{lat},{lng});
  node["railway"="station"](around:{radius},{lat},{lng});
  node["railway"="subway_entrance"](around:{radius},{lat},{lng});
);
out body 80;
"""
    body = urllib.parse.urlencode({'data': query}).encode('utf-8')
    last_error = None
    for url in OVERPASS_ENDPOINTS:
        req = urllib.request.Request(
            url,
            data=body,
            headers={'User-Agent': 'SmartLivingSystem/1.0 (poi-overlay)'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
            return payload.get('elements') or []
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = exc
            continue
    if last_error:
        return []
    return []


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
