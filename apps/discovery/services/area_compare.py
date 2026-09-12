"""Compare living areas using published listing aggregates."""
from __future__ import annotations

from django.db.models import Avg, Count, Q

from listings.models import ListingStatus, Property
from listings.services.living_cost import estimate_living_cost

TRANSPORT_KEYS = ('bus', 'metro', 'station', 'cng', 'rickshaw', 'launch')
MARKET_KEYS = ('market', 'bazar', 'bazaar', 'shop', 'mall', 'super shop')


def list_areas(city: str | None = None, limit: int = 40) -> list[dict]:
    qs = _published().exclude(area='')
    if city:
        qs = qs.filter(city__iexact=city.strip())
    rows = (
        qs.values('area', 'city')
        .annotate(
            listingCount=Count('id'),
            averageRent=Avg('rent'),
        )
        .order_by('-listingCount', 'area')[:limit]
    )
    return [
        {
            'area': row['area'],
            'city': row['city'],
            'listingCount': row['listingCount'],
            'averageRent': round(float(row['averageRent'] or 0)),
        }
        for row in rows
    ]


def compare_areas(names: list[str], city: str | None = None) -> dict:
    cleaned = []
    seen = set()
    for raw in names:
        name = (raw or '').strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)
    cleaned = cleaned[:4]
    if len(cleaned) < 2:
        from core.exceptions import InvalidError

        raise InvalidError('Provide at least two area names to compare.')

    results = [summarize_area(name, city) for name in cleaned]
    recommendation = _recommend(results)
    return {
        'areas': results,
        'recommendation': recommendation,
    }


def summarize_area(area: str, city: str | None = None) -> dict:
    qs = _published().filter(area__iexact=area.strip())
    if city:
        qs = qs.filter(city__iexact=city.strip())
    total = qs.count()
    if total == 0:
        return {
            'area': area,
            'city': city or '',
            'listingCount': 0,
            'averageRent': 0,
            'verifiedPercent': 0,
            'securityPercent': 0,
            'parkingPercent': 0,
            'averageRating': 0,
            'transportScore': 0,
            'marketAccess': 0,
            'safetyScore': 0,
            'livingCost': None,
        }

    agg = qs.aggregate(
        averageRent=Avg('rent'),
        averageRating=Avg('rating'),
        verifiedCount=Count('id', filter=Q(verified=True) | Q(verification_status='verified')),
        securityCount=Count('id', filter=Q(security=True)),
        parkingCount=Count('id', filter=Q(parking=True)),
    )
    listings = list(qs.only('nearby_facilities', 'security', 'verified', 'rating', 'city', 'type'))
    transport = _keyword_score(listings, TRANSPORT_KEYS)
    market = _keyword_score(listings, MARKET_KEYS)
    avg_rent = round(float(agg['averageRent'] or 0))
    avg_rating = round(float(agg['averageRating'] or 0), 2)
    verified_pct = round(100 * (agg['verifiedCount'] or 0) / total)
    security_pct = round(100 * (agg['securityCount'] or 0) / total)
    parking_pct = round(100 * (agg['parkingCount'] or 0) / total)
    safety = min(
        100,
        round(0.4 * security_pct + 0.3 * verified_pct + 0.3 * min(100, avg_rating * 20)),
    )
    city_name = city or (listings[0].city if listings else '')
    from listings.services.living_cost import living_cost_for_property

    costs = [
        living_cost_for_property(prop)
        for prop in qs.prefetch_related('linked_messes', 'linked_flats')[:80]
    ]
    living = _average_living_cost(costs) if costs else estimate_living_cost(rent=avg_rent)
    return {
        'area': listings[0].area if listings else area,
        'city': city_name,
        'listingCount': total,
        'averageRent': avg_rent,
        'verifiedPercent': verified_pct,
        'securityPercent': security_pct,
        'parkingPercent': parking_pct,
        'averageRating': avg_rating,
        'transportScore': transport,
        'marketAccess': market,
        'safetyScore': safety,
        'livingCost': living,
    }


def _published():
    return Property.objects.filter(
        published=True,
        listing_status=ListingStatus.PUBLISHED,
        flagged_unavailable_at__isnull=True,
    )


def _keyword_score(listings: list, keys: tuple[str, ...]) -> int:
    if not listings:
        return 0
    hits = 0
    for prop in listings:
        blob = ' '.join(str(x).lower() for x in (prop.nearby_facilities or []))
        if any(k in blob for k in keys):
            hits += 1
    return round(100 * hits / len(listings))


def _average_living_cost(costs: list[dict]) -> dict:
    keys = ('rent', 'serviceCharge', 'electricity', 'gas', 'internet', 'water', 'transport', 'meals')
    count = len(costs) or 1
    parts = {key: round(sum(item.get(key) or 0 for item in costs) / count) for key in keys}
    return {
        **parts,
        'total': sum(parts.values()),
        'currency': 'BDT',
        'shared': False,
        'note': 'Average of owner estimates on listings in this area.',
    }


def _recommend(results: list[dict]) -> dict:
    scored = []
    for row in results:
        if not row['listingCount']:
            continue
        cost = (row['livingCost'] or {}).get('total') or row['averageRent'] or 1
        # Lower cost and higher safety/transport win
        value = (
            0.35 * row['safetyScore']
            + 0.25 * row['transportScore']
            + 0.15 * row['marketAccess']
            + 0.15 * min(100, row['averageRating'] * 20)
            + 0.10 * max(0, 100 - min(100, cost / 400))
        )
        scored.append((value, row))
    if not scored:
        return {
            'area': results[0]['area'] if results else '',
            'reason': 'Not enough live listings to recommend an area yet.',
        }
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0][1]
    cheapest = min(results, key=lambda r: r['averageRent'] or 10**9)
    if cheapest['area'] != best['area'] and cheapest['listingCount']:
        reason = (
            f"{best['area']} scores highest for safety and access. "
            f"{cheapest['area']} is cheaper on average rent "
            f"(৳{cheapest['averageRent']:,}/mo)."
        )
    else:
        reason = (
            f"{best['area']} currently offers the best mix of safety, "
            f"transport, and living cost among the selected areas."
        )
    return {'area': best['area'], 'reason': reason}
