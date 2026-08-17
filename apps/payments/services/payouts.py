"""Owner payout settlement and analytics."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone

from core.exceptions import ForbiddenError, NotFoundError
from payments.models import OwnerPayout, PayoutStatus
from payments.services.helpers import commission_display_rate


def _owner_payout(owner, payout_id) -> OwnerPayout:
    try:
        payout = OwnerPayout.objects.get(pk=payout_id)
    except OwnerPayout.DoesNotExist as exc:
        raise NotFoundError('Payout not found.') from exc
    if payout.owner_id != owner.id and owner.role != 'admin':
        raise ForbiddenError('You cannot access this payout.')
    return payout


def settle_payout(owner, payout_id) -> OwnerPayout:
    payout = _owner_payout(owner, payout_id)
    payout.status = PayoutStatus.PAID
    payout.payout_date = timezone.now().date()
    payout.save(update_fields=['status', 'payout_date', 'updated_at'])
    return payout


def owner_analytics(owner) -> dict:
    qs = OwnerPayout.objects.filter(owner=owner)

    totals = qs.aggregate(
        total_collected=Sum('gross_amount'),
        total_commission=Sum('commission_amount'),
        net_earnings=Sum('net_amount'),
    )
    pending = qs.filter(status=PayoutStatus.PENDING).aggregate(total=Sum('net_amount'))['total'] or Decimal('0')
    paid = qs.filter(status=PayoutStatus.PAID).aggregate(total=Sum('net_amount'))['total'] or Decimal('0')

    by_method = (
        qs.values('payment_method')
        .annotate(amount=Sum('gross_amount'), count=Count('id'))
        .order_by('-amount')
    )
    collection_by_method = [
        {
            'method': row['payment_method'],
            'amount': float(row['amount'] or 0),
            'count': row['count'],
        }
        for row in by_method
    ]

    monthly: dict[str, dict] = defaultdict(lambda: {'gross': Decimal('0'), 'net': Decimal('0')})
    for payout in qs.filter(paid_at__isnull=False).order_by('paid_at'):
        month_key = payout.paid_at.strftime('%Y-%m')
        monthly[month_key]['gross'] += payout.gross_amount
        monthly[month_key]['net'] += payout.net_amount

    monthly_trend = [
        {'month': month, 'gross': float(data['gross']), 'net': float(data['net'])}
        for month, data in sorted(monthly.items())
    ]

    return {
        'totalCollected': float(totals['total_collected'] or 0),
        'totalCommission': float(totals['total_commission'] or 0),
        'netEarnings': float(totals['net_earnings'] or 0),
        'pendingPayouts': float(pending),
        'paidPayouts': float(paid),
        'collectionByMethod': collection_by_method,
        'monthlyTrend': monthly_trend,
        'commissionRate': float(commission_display_rate()),
    }
