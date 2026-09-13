"""AI Property Matching — natural language query → ranked results with match scores."""
from __future__ import annotations

import re
from typing import Any

from django.db.models import Q

from listings.models import ListingStatus, Property
from listings.services.public_catalog import (
    public_apartment_visibility_q,
    unique_public_listings,
)


# Bangla and English keyword maps
AREA_ALIASES = {
    'mohammadpur': ['mohammadpur', 'মোহাম্মদপুর'],
    'mirpur': ['mirpur', 'মিরপুর'],
    'dhanmondi': ['dhanmondi', 'ধানমন্ডি'],
    'uttara': ['uttara', 'উত্তরা'],
    'bashundhara': ['bashundhara', 'বসুন্ধরা'],
    'gulshan': ['gulshan', 'গুলশান'],
    'banani': ['banani', 'বনানী'],
    'motijheel': ['motijheel', 'মতিঝিল'],
    'farmgate': ['farmgate', 'ফার্মগেট'],
    'shahbag': ['shahbag', 'শাহবাগ'],
    'khilgaon': ['khilgaon', 'খিলগাঁও'],
    'badda': ['badda', 'বাড্ডা'],
    'rampura': ['rampura', 'রামপুরা'],
    'tejgaon': ['tejgaon', 'তেজগাঁও'],
    'lalmatia': ['lalmatia', 'লালমাটিয়া'],
    'jigatala': ['jigatala', 'জিগাতলা'],
    'azimpur': ['azimpur', 'আজিমপুর'],
    'old dhaka': ['old dhaka', 'পুরান ঢাকা'],
    'sylhet': ['sylhet', 'সিলেট'],
    'chattogram': ['chattogram', 'chittagong', 'চট্টগ্রাম'],
    'rajshahi': ['rajshahi', 'রাজশাহী'],
    'khulna': ['khulna', 'খুলনা'],
    'rangpur': ['rangpur', 'রংপুর'],
    'coxs bazar': ['coxs bazar', "cox's bazar", 'কক্সবাজার'],
}

TYPE_KEYWORDS = {
    'apartment': ['apartment', 'flat', 'ফ্ল্যাট', 'অ্যাপার্টমেন্ট', 'বাসা', 'basa'],
    'mess': ['mess', 'মেস', 'hostel', 'হোস্টেল', 'seat', 'সিট'],
    'hostel': ['hostel', 'হোস্টেল', 'ছাত্রাবাস'],
}

GENDER_KEYWORDS = {
    'male': [
        'male', 'boys', 'boy', 'chele', 'cheleder',
        'ছেলে', 'ছেলেদের', 'bachelor', 'ব্যাচেলর',
    ],
    'female': [
        'female', 'girls', 'girl', 'meye', 'meyeder',
        'মেয়ে', 'মেয়েদের', 'মহিলা', 'ladies',
    ],
    'family': ['family', 'ফ্যামিলি', 'পরিবার'],
}

FACILITY_KEYWORDS = {
    'lift': ['lift', 'elevator', 'লিফট'],
    'generator': ['generator', 'জেনারেটর', 'ips'],
    'wifi': ['wifi', 'wi-fi', 'internet', 'ইন্টারনেট', 'ওয়াইফাই'],
    'ac': ['ac', 'air condition', 'এসি'],
    'parking': ['parking', 'পার্কিং', 'গাড়ি'],
    'security': ['security', 'guard', 'cctv', 'নিরাপত্তা', 'সিকিউরিটি'],
    'attached bath': ['attached bath', 'attached bathroom', 'attached washroom', 'অ্যাটাচড বাথ'],
    'balcony': ['balcony', 'ব্যালকনি', 'বারান্দা'],
    'gas': ['gas', 'গ্যাস'],
    'water': ['water', 'পানি', '24/7 water'],
}

# Bangla digit conversion
BANGLA_DIGITS = str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789')


def _normalize(text: str) -> str:
    """Lowercase, convert Bangla digits, strip extra whitespace."""
    return text.lower().translate(BANGLA_DIGITS).strip()


def _extract_budget(text: str) -> tuple[float | None, float | None]:
    """Extract budget range from natural language."""
    normalized = _normalize(text)
    # "15000 টাকা" or "15,000" or "৳15000" or "budget 15000"
    amounts = re.findall(r'[\d,]+(?:\.\d+)?', normalized.replace(',', ''))
    amounts = [float(a) for a in amounts if 500 <= float(a) <= 500000]

    if len(amounts) >= 2:
        return min(amounts), max(amounts)
    if len(amounts) == 1:
        budget = amounts[0]
        # ±30% range
        return budget * 0.7, budget * 1.3
    return None, None


def _extract_bedrooms(text: str) -> int | None:
    normalized = _normalize(text)
    match = re.search(r'(\d+)\s*(?:bed(?:room)?|বেডরুম|রুম|room)', normalized)
    if match:
        return int(match.group(1))
    return None


def _place_aliases(place: str) -> list[str]:
    key = (place or '').strip().lower()
    return AREA_ALIASES.get(key, [key])


def _listing_text(prop: Property) -> str:
    return ' '.join(
        part
        for part in (prop.name, prop.area, prop.address, prop.city)
        if part
    ).lower()


def _mentions_place(prop: Property, place: str) -> bool:
    blob = _listing_text(prop)
    return any(alias in blob for alias in _place_aliases(place))


def _extract_area(text: str) -> str | None:
    normalized = _normalize(text)
    for area, aliases in AREA_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                return area
    return None


def _extract_city(text: str) -> str | None:
    normalized = _normalize(text)
    cities = {
        'dhaka': ['dhaka', 'ঢাকা'],
        'chattogram': ['chattogram', 'chittagong', 'চট্টগ্রাম'],
        'sylhet': ['sylhet', 'সিলেট'],
        'rajshahi': ['rajshahi', 'রাজশাহী'],
        'khulna': ['khulna', 'খুলনা'],
        'rangpur': ['rangpur', 'রংপুর'],
    }
    for city, aliases in cities.items():
        for alias in aliases:
            if alias in normalized:
                return city
    return None


def _extract_type(text: str) -> str | None:
    normalized = _normalize(text)
    for ptype, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in normalized:
                return ptype
    return None


def _extract_gender(text: str) -> str | None:
    normalized = _normalize(text)
    for gender, keywords in GENDER_KEYWORDS.items():
        for kw in keywords:
            if kw in normalized:
                if gender == 'family':
                    return 'mixed'
                return gender
    return None


def _extract_facilities(text: str) -> list[str]:
    normalized = _normalize(text)
    found = []
    for facility, keywords in FACILITY_KEYWORDS.items():
        for kw in keywords:
            if kw in normalized:
                found.append(facility)
                break
    return found


def parse_natural_query(query: str) -> dict[str, Any]:
    """Parse a natural language query into structured filters (LLM then rules)."""
    from listings.services.ai_llm import llm_parse_query

    llm = llm_parse_query(query)
    if llm:
        # Merge any missing keys from rules for robustness
        rules = _parse_natural_query_rules(query)
        for key, value in rules.items():
            if key == 'rawQuery':
                continue
            if llm.get(key) in (None, [], ''):
                llm[key] = value
        return llm
    return _parse_natural_query_rules(query)


def _parse_natural_query_rules(query: str) -> dict[str, Any]:
    """Rule/keyword parser (Bangla + English)."""
    budget_min, budget_max = _extract_budget(query)
    return {
        'area': _extract_area(query),
        'city': _extract_city(query),
        'type': _extract_type(query),
        'gender': _extract_gender(query),
        'budgetMin': budget_min,
        'budgetMax': budget_max,
        'bedrooms': _extract_bedrooms(query),
        'facilities': _extract_facilities(query),
        'rawQuery': query,
        'parser': 'rules',
    }


def compute_match_score(prop: Property, parsed: dict[str, Any]) -> float:
    """Compute 0–100 match score for a property against parsed query."""
    score = 0.0
    max_score = 0.0

    # Area match (30 points)
    if parsed.get('area'):
        max_score += 30
        prop_area = (prop.area or '').lower()
        prop_city = (prop.city or '').lower()
        target = parsed['area'].lower()
        aliases = _place_aliases(target)
        if any(a in prop_area for a in aliases):
            score += 30
        elif _mentions_place(prop, target):
            score += 30
        elif any(a in prop_city for a in aliases):
            score += 15

    # City match (15 points)
    if parsed.get('city'):
        max_score += 15
        if (prop.city or '').lower() == parsed['city'].lower():
            score += 15

    # Budget match (25 points)
    if parsed.get('budgetMin') is not None:
        max_score += 25
        rent = float(prop.rent)
        budget_min = parsed['budgetMin']
        budget_max = parsed['budgetMax'] or budget_min * 1.3
        if budget_min <= rent <= budget_max:
            score += 25
        elif rent < budget_min:
            # Under budget is okay
            ratio = rent / budget_min
            score += 25 * max(0, ratio)
        else:
            # Over budget penalty
            over = (rent - budget_max) / budget_max
            score += 25 * max(0, 1 - over * 2)

    # Type match (15 points)
    if parsed.get('type'):
        max_score += 15
        if prop.type == parsed['type']:
            score += 15

    # Gender match (10 points)
    if parsed.get('gender'):
        max_score += 10
        if prop.gender == parsed['gender'] or prop.gender == 'mixed':
            score += 10

    # Facility match (up to 15 points)
    if parsed.get('facilities'):
        max_score += 15
        prop_facilities = [f.lower() for f in (prop.facilities or [])]
        matched = sum(
            1 for f in parsed['facilities']
            if any(f in pf for pf in prop_facilities)
        )
        if parsed['facilities']:
            score += 15 * (matched / len(parsed['facilities']))

    # Bonus: verified (+3), instant book (+2)
    max_score += 5
    if prop.verified:
        score += 3
    if prop.instant_book:
        score += 2

    if max_score == 0:
        return 50.0  # No filters = neutral score
    return round(min(100, (score / max_score) * 100), 1)


def ai_match_properties(query: str, *, limit: int = 20) -> dict[str, Any]:
    """Main entry: parse query → score all properties → return ranked results."""
    parsed = parse_natural_query(query)

    # Build base queryset
    qs = Property.objects.filter(
        published=True,
        listing_status=ListingStatus.PUBLISHED,
        flagged_unavailable_at__isnull=True,
        available=True,
    ).filter(
        public_apartment_visibility_q()
    ).distinct().select_related('owner').prefetch_related(
        'image_files',
        'linked_messes',
        'linked_flats__building',
    )

    # Pre-filter by city/area if detected (performance)
    if parsed.get('city'):
        qs = qs.filter(city__iexact=parsed['city'])
    if parsed.get('type'):
        qs = qs.filter(type=parsed['type'])

    candidates = unique_public_listings(list(qs[:200]))
    place = parsed.get('area')
    if place:
        located = [prop for prop in candidates if _mentions_place(prop, place)]
        if located:
            candidates = located

    # Score each
    scored = []
    for prop in candidates:
        match_score = compute_match_score(prop, parsed)
        scored.append((prop, match_score))

    # Sort by score desc
    scored.sort(key=lambda x: x[1], reverse=True)

    return {
        'parsedQuery': parsed,
        'results': scored[:limit],
        'totalCandidates': len(candidates),
    }
