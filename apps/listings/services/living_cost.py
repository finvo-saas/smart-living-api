"""Estimated total monthly living cost for a listing (Bangladesh defaults)."""
from __future__ import annotations

from listings.models import Property, PropertyType

CITY_MULTIPLIER = {
    'dhaka': 1.0,
    'chattogram': 0.92,
    'chittagong': 0.92,
    'sylhet': 0.88,
    'rajshahi': 0.82,
    'khulna': 0.82,
    'rangpur': 0.78,
}

TRANSPORT_BY_AREA = {
    'gulshan': 1800,
    'banani': 1800,
    'baridhara': 1800,
    'uttara': 2200,
    'dhanmondi': 2000,
    'mohammadpur': 2200,
    'mirpur': 2300,
    'bashundhara': 2400,
    'badda': 2500,
    'khilgaon': 2500,
    'old dhaka': 2100,
}


def living_cost_for_property(prop: Property) -> dict:
    meal_cost = float(prop.meal_cost) if prop.meal_cost is not None else None
    return estimate_living_cost(
        rent=float(prop.rent or 0),
        city=prop.city or '',
        area=prop.area or '',
        property_type=prop.type,
        meal_included=bool(prop.meal_included),
        meal_cost=meal_cost,
    )


def estimate_living_cost(
    *,
    rent: float,
    city: str,
    area: str = '',
    property_type: str = PropertyType.APARTMENT,
    meal_included: bool = False,
    meal_cost: float | None = None,
) -> dict:
    is_shared = property_type in (PropertyType.MESS, PropertyType.HOSTEL)
    mult = CITY_MULTIPLIER.get((city or '').strip().lower(), 0.9)

    electricity = (800 if is_shared else 1500) * mult
    gas = (400 if is_shared else 900) * mult
    internet = (500 if is_shared else 800) * mult
    water = (200 if is_shared else 400) * mult
    transport = _transport(area) * mult

    if meal_included:
        meals = float(meal_cost or 0)
    elif is_shared:
        meals = 4500 * mult
    else:
        meals = 0.0

    parts = {
        'rent': round(rent),
        'electricity': round(electricity),
        'gas': round(gas),
        'internet': round(internet),
        'water': round(water),
        'transport': round(transport),
        'meals': round(meals),
    }
    total = sum(parts.values())
    return {
        **parts,
        'total': total,
        'currency': 'BDT',
        'shared': is_shared,
        'note': 'Estimates for typical Bangladesh household usage. Actual bills vary.',
    }


def _transport(area: str) -> float:
    key = (area or '').strip().lower()
    if key in TRANSPORT_BY_AREA:
        return TRANSPORT_BY_AREA[key]
    for name, value in TRANSPORT_BY_AREA.items():
        if name in key:
            return value
    return 2500
