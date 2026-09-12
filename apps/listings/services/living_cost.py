"""Monthly living cost from amounts the owner stored.

Mess and hostel bills are house totals, divided by total seats.
Apartment bills are already per flat. Transport is not included.
Missing amounts are omitted, not guessed.
"""
from __future__ import annotations

from listings.models import Property, PropertyType

BILL_ATTRS = (
    'electricity_bill',
    'gas_bill',
    'internet_bill',
    'water_bill',
)


def living_cost_for_property(prop: Property) -> dict:
    source = prop
    seats = 0
    if prop.type in (PropertyType.MESS, PropertyType.HOSTEL):
        mess = prop.linked_messes.filter(is_deleted=False).first()
        if mess is not None:
            source = mess
            seats = int(mess.total_seats or 0)
        meal_cost = getattr(source, 'meal_monthly_charge', None)
        if meal_cost is None:
            meal_cost = prop.meal_cost
        meal_included = meal_cost is not None or bool(prop.meal_included)
    else:
        flat = None
        if prop.type == PropertyType.APARTMENT:
            flat = prop.linked_flats.order_by('created_at').first()
        if flat is not None and _has_bills(flat):
            source = flat
        meal_cost = prop.meal_cost
        meal_included = bool(prop.meal_included)
    return estimate_living_cost(
        rent=float(prop.rent or 0),
        property_type=prop.type,
        meal_included=meal_included,
        meal_cost=float(meal_cost) if meal_cost is not None else None,
        electricity=_amount(source, 'electricity_bill'),
        gas=_amount(source, 'gas_bill'),
        internet=_amount(source, 'internet_bill'),
        water=_amount(source, 'water_bill'),
        service_charge=_amount(prop, 'service_charge'),
        seats=seats,
    )


def estimate_living_cost(
    *,
    rent: float,
    property_type: str = PropertyType.APARTMENT,
    meal_included: bool = False,
    meal_cost: float | None = None,
    electricity: float | None = None,
    gas: float | None = None,
    internet: float | None = None,
    water: float | None = None,
    service_charge: float | None = None,
    seats: int = 0,
    city: str = '',
    area: str = '',
) -> dict:
    del city, area
    is_shared = property_type in (PropertyType.MESS, PropertyType.HOSTEL)
    seats = int(seats or 0)
    if is_shared and seats > 0:
        share = lambda value: _share(value, seats)
        note = (
            f'Per seat. House electricity, gas, internet, and water '
            f'are divided by {seats} seats.'
        )
    elif is_shared:
        share = lambda value: 0
        note = 'Add seat capacity on the mess so house bills can be split per seat.'
    elif property_type == PropertyType.APARTMENT:
        share = lambda value: _share(value, 1)
        note = 'Per flat. These are the owner’s monthly estimates. Actual bills vary.'
    else:
        share = lambda value: _share(value, 1)
        note = 'Owner monthly estimates. Actual bills vary.'

    meals = float(meal_cost) if meal_included and meal_cost else 0.0
    parts = {
        'rent': round(rent),
        'serviceCharge': round(float(service_charge)) if service_charge else 0,
        'electricity': share(electricity),
        'gas': share(gas),
        'internet': share(internet),
        'water': share(water),
        'transport': 0,
        'meals': round(meals),
    }
    return {
        **parts,
        'total': sum(parts.values()),
        'currency': 'BDT',
        'shared': is_shared,
        'note': note,
    }


def _has_bills(obj) -> bool:
    return any(getattr(obj, name, None) is not None for name in BILL_ATTRS)


def _amount(obj, name: str) -> float | None:
    value = getattr(obj, name, None)
    if value is None:
        return None
    return float(value)


def _share(value: float | None, seats: int) -> int:
    if value is None or seats <= 0:
        return 0
    return round(float(value) / seats)
