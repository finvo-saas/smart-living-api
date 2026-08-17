from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from hotels.models import DEFAULT_CANCELLATION, Hotel, HotelBooking


def _parse_time(value: str) -> time:
    parts = (value or '14:00').split(':')
    return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def _hours_until_check_in(booking: HotelBooking, hotel: Hotel) -> float:
    check_in_time = _parse_time(booking.check_in_time or hotel.check_in_time)
    check_in_dt = timezone.make_aware(
        datetime.combine(booking.check_in, check_in_time),
    )
    now = timezone.now()
    delta = check_in_dt - now
    return max(delta.total_seconds() / 3600, 0)


def calculate_cancellation_refund(
    booking: HotelBooking,
    hotel: Hotel | None = None,
) -> dict:
    hotel = hotel or booking.hotel
    policy = hotel.cancellation_policy or DEFAULT_CANCELLATION

    free_hours = int(policy.get('freeCancellationHours', 48))
    partial_hours = int(policy.get('partialRefundHours', 24))
    partial_percent = int(policy.get('partialRefundPercent', 50))
    no_refund_hours = int(policy.get('noRefundWithinHours', 24))

    hours_until = _hours_until_check_in(booking, hotel)
    paid_amount = Decimal(booking.advance_amount or 0)
    if booking.payment_status == 'paid':
        paid_amount = Decimal(booking.total_amount)
    elif booking.payment_status == 'partial':
        paid_amount = Decimal(booking.advance_amount or 0)

    if hours_until >= free_hours:
        refund_percent = 100
        policy_applied = 'full_refund'
    elif hours_until >= no_refund_hours:
        refund_percent = partial_percent
        policy_applied = 'partial_refund'
    else:
        refund_percent = 0
        policy_applied = 'no_refund'

    refund_amount = (
        paid_amount * Decimal(refund_percent) / Decimal(100)
    ).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    return {
        'refundAmount': int(refund_amount),
        'refundPercent': refund_percent,
        'policyApplied': policy_applied,
        'hoursUntilCheckIn': round(hours_until, 1),
        'partialRefundHours': partial_hours,
    }
