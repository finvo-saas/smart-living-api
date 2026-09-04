"""Persist nearby POI labels onto a property from OpenStreetMap."""
from __future__ import annotations

from listings.models import Property


def refresh_nearby_facilities(prop: Property, radius: int = 1200) -> list[str]:
    if prop.latitude is None or prop.longitude is None:
        return list(prop.nearby_facilities or [])
    from discovery.services.pois import nearby_pois

    payload = nearby_pois(float(prop.latitude), float(prop.longitude), radius=radius)
    labels: list[str] = []
    for category, items in (payload.get('pois') or {}).items():
        for item in items[:2]:
            name = (item.get('name') or category).strip()
            dist = item.get('distanceM')
            if dist is not None:
                labels.append(f'{category}: {name} ({dist}m)')
            else:
                labels.append(f'{category}: {name}')
    # Keep unique, prefer fresh OSM labels but preserve owner-entered extras
    osm_prefixes = ('hospital:', 'school:', 'market:', 'mosque:', 'bus:', 'metro:')
    existing = [
        x for x in (prop.nearby_facilities or [])
        if not str(x).lower().startswith(osm_prefixes)
    ]
    merged = existing + labels
    seen = set()
    out = []
    for item in merged:
        key = str(item).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    prop.nearby_facilities = out[:24]
    prop.save(update_fields=['nearby_facilities', 'updated_at'])
    return prop.nearby_facilities
