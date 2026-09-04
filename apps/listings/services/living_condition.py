"""Composite Living Condition Score (0–100) for a listing."""
from __future__ import annotations

from listings.models import Property


FACILITY_BUCKETS = {
    'food': ('meal', 'kitchen', 'dining', 'cook', 'খাবার', 'রান্না'),
    'water': ('water', 'পানি', 'filter', 'pump'),
    'electricity': ('generator', 'ips', 'electric', 'বিদ্যুৎ', 'জেনারেটর'),
    'security': ('security', 'cctv', 'guard', 'gate', 'নিরাপত্তা', 'সিকিউরিটি'),
    'cleanliness': ('clean', 'laundry', 'housekeep', 'পরিচ্ছন্ন'),
    'internet': ('wifi', 'wi-fi', 'internet', 'broadband', 'ওয়াইফাই'),
    'bathroom': ('bathroom', 'washroom', 'attached bath', 'toilet', 'বাথ'),
    'location': ('lift', 'balcony', 'parking', 'elevator', 'লিফট'),
}


def living_condition_for_property(prop: Property) -> dict:
    facilities = [str(f).lower() for f in (prop.facilities or [])]
    blob = ' '.join(facilities)
    review_avgs = _review_category_avgs(prop)

    breakdown = []
    for key, keywords in FACILITY_BUCKETS.items():
        facility_hit = any(k in blob for k in keywords)
        review_val = review_avgs.get(key)
        if key == 'security' and prop.security:
            facility_hit = True
        if key == 'food' and prop.meal_included:
            facility_hit = True
        if key == 'location' and (prop.latitude is not None or prop.parking):
            facility_hit = facility_hit or bool(prop.parking) or prop.latitude is not None

        if review_val is not None:
            earned = round(review_val * 2.5)  # 1–5 → ~2.5–12.5, cap later
            max_points = 12.5
        else:
            earned = 10 if facility_hit else (4 if facilities else 0)
            max_points = 12.5
        earned = min(max_points, earned)
        breakdown.append({
            'key': key,
            'label': key.replace('_', ' ').title(),
            'earned': round(earned, 1),
            'max': max_points,
            'passed': earned >= max_points * 0.7,
        })

    # Normalize to 100
    total_earned = sum(i['earned'] for i in breakdown)
    total_max = sum(i['max'] for i in breakdown) or 1
    score = round(100 * total_earned / total_max)
    if score >= 85:
        label = 'Excellent living conditions'
    elif score >= 70:
        label = 'Good living conditions'
    elif score >= 50:
        label = 'Average living conditions'
    else:
        label = 'Needs improvement'
    return {'score': score, 'label': label, 'breakdown': breakdown}


def _review_category_avgs(prop: Property) -> dict[str, float]:
    from django.db.models import Avg

    from listings.models import PropertyReview

    mapping = {
        'cleanliness': 'cleanliness',
        'security': 'security',
        'location': 'location',
        'food': None,  # no direct review field
        'water': None,
        'electricity': None,
        'internet': None,
        'bathroom': None,
    }
    agg = PropertyReview.objects.filter(property=prop).aggregate(
        cleanliness=Avg('cleanliness'),
        security=Avg('security'),
        location=Avg('location'),
        value=Avg('value_for_money'),
    )
    out = {}
    for key, field in mapping.items():
        if field and agg.get(field) is not None:
            out[key] = float(agg[field])
    # Soft-map value_for_money into food/internet hints when present
    if agg.get('value') is not None:
        out.setdefault('food', float(agg['value']))

    # Prefer linked mess utility reliability for water / electricity buckets
    linked = getattr(prop, 'linked_messes', None)
    mess = linked.filter(is_deleted=False).first() if linked is not None else None
    if mess is not None:
        from mess.services.reliability import electricity_reliability, water_reliability

        water = water_reliability(mess)
        electric = electricity_reliability(mess)
        # Convert 0–100 reliability → 1–5 review-like scale for scoring
        out['water'] = max(1.0, min(5.0, water['score'] / 20))
        out['electricity'] = max(1.0, min(5.0, electric['score'] / 20))
    return out
