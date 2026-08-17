from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from hotels.models import DEFAULT_PRICING_RULES, Hotel, Room


def _is_weekend_night(d: date) -> bool:
    return d.weekday() in (4, 5)  # Fri=4, Sat=5 in Python (Mon=0)


def _seasonal_multiplier(d: date, rules: dict) -> float:
    key = d.isoformat()
    mult = 1.0
    for rule in rules.get('seasonalRules') or []:
        start = rule.get('startDate', '')
        end = rule.get('endDate', '')
        if start <= key < end:
            mult = max(mult, float(rule.get('multiplier', 1)))
    return mult


def _round_money(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def calculate_booking_fees(
    room: Room,
    check_in: date,
    check_out: date,
    hotel: Hotel | None = None,
) -> dict:
    nights = (check_out - check_in).days
    advance_percent = (hotel.advance_payment_percent if hotel else 30) or 30
    rules = (hotel.pricing_rules if hotel and hotel.pricing_rules else None) or DEFAULT_PRICING_RULES

    if nights <= 0:
        return {
            'nights': 0,
            'baseRoomTotal': 0,
            'weekendNights': 0,
            'weekendSurcharge': 0,
            'seasonalSurcharge': 0,
            'subtotal': 0,
            'serviceCharge': 0,
            'vat': 0,
            'total': 0,
            'advanceAmount': 0,
            'remainingAmount': 0,
            'advancePercent': advance_percent,
        }

    base_price = float(room.base_price)
    weekend_multiplier = float(rules.get('weekendMultiplier', 1.15))
    service_pct = float(rules.get('serviceChargePercent', 10))
    vat_pct = float(rules.get('vatPercent', 15))

    base_room_total = 0.0
    weekend_nights = 0
    weekend_surcharge = 0.0
    seasonal_surcharge = 0.0

    night = check_in
    while night < check_out:
        base = base_price
        base_room_total += base
        night_price = base

        if _is_weekend_night(night) and weekend_multiplier > 1:
            extra = base * (weekend_multiplier - 1)
            weekend_surcharge += extra
            night_price += extra
            weekend_nights += 1

        season_mult = _seasonal_multiplier(night, rules)
        if season_mult > 1:
            seasonal_surcharge += night_price * (season_mult - 1)

        night += timedelta(days=1)

    subtotal = _round_money(base_room_total + weekend_surcharge + seasonal_surcharge)
    service_charge = _round_money(subtotal * service_pct / 100)
    vat = _round_money((subtotal + service_charge) * vat_pct / 100)
    total = subtotal + service_charge + vat
    advance_amount = _round_money(total * advance_percent / 100)
    remaining_amount = total - advance_amount

    return {
        'nights': nights,
        'baseRoomTotal': _round_money(base_room_total),
        'weekendNights': weekend_nights,
        'weekendSurcharge': _round_money(weekend_surcharge),
        'seasonalSurcharge': _round_money(seasonal_surcharge),
        'subtotal': subtotal,
        'serviceCharge': service_charge,
        'vat': vat,
        'total': total,
        'advanceAmount': advance_amount,
        'remainingAmount': remaining_amount,
        'advancePercent': advance_percent,
    }


def room_pricing_for_range(
    room: Room,
    start: date,
    end: date,
    hotel: Hotel | None = None,
) -> list[dict]:
    rules = (hotel.pricing_rules if hotel and hotel.pricing_rules else None) or DEFAULT_PRICING_RULES
    weekend_multiplier = float(rules.get('weekendMultiplier', 1.15))
    base_price = float(room.base_price)
    results = []
    current = start
    while current <= end:
        is_weekend = _is_weekend_night(current)
        price = base_price
        if is_weekend and weekend_multiplier > 1:
            price = base_price * weekend_multiplier
        season_mult = _seasonal_multiplier(current, rules)
        if season_mult > 1:
            price *= season_mult
        price_int = _round_money(price)
        results.append({
            'roomId': str(room.id),
            'date': current.isoformat(),
            'price': price_int,
            'isWeekend': is_weekend,
            'isSpecialOffer': False,
            'offerPrice': None,
        })
        current += timedelta(days=1)
    return results
