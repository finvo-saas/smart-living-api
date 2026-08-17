"""Shared payment completion helpers."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from billing.models import Bill, BillStatus
from payments.models import (
    OwnerPayout,
    PaymentMethod,
    PaymentTransaction,
    PaymentTransactionStatus,
    PayoutStatus,
)


def commission_display_rate() -> Decimal:
    """Percent for frontend display, e.g. 5.0 for COMMISSION_RATE=0.05."""
    return Decimal(str(settings.COMMISSION_RATE * 100))


def calc_commission(gross: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    rate_pct = commission_display_rate()
    commission_amount = (gross * Decimal(str(settings.COMMISSION_RATE))).quantize(Decimal('0.01'))
    net_amount = gross - commission_amount
    return rate_pct, commission_amount, net_amount


def mark_bill_paid(bill: Bill | None) -> None:
    if bill is None or bill.status == BillStatus.PAID:
        return
    bill.status = BillStatus.PAID
    bill.paid_date = timezone.now().date()
    bill.save(update_fields=['status', 'paid_date', 'updated_at'])


def create_owner_payout(
    *,
    txn: PaymentTransaction,
    bill: Bill | None,
    payout_status: str | None = None,
) -> OwnerPayout | None:
    if bill is None:
        return None

    existing = OwnerPayout.objects.filter(payment_transaction=txn).first()
    if existing:
        return existing

    rate_pct, commission_amount, net_amount = calc_commission(txn.amount)
    if payout_status is None:
        payout_status = (
            PayoutStatus.PAID
            if txn.payment_method == PaymentMethod.CASH
            else PayoutStatus.PENDING
        )

    paid_at = txn.completed_at or timezone.now()
    return OwnerPayout.objects.create(
        owner=bill.owner,
        bill=bill,
        payment_transaction=txn,
        bill_name=txn.bill_name,
        tenant_name=txn.tenant_name or bill.tenant_name,
        property_name=txn.property_name or bill.property_name,
        gross_amount=txn.amount,
        commission_rate=rate_pct,
        commission_amount=commission_amount,
        net_amount=net_amount,
        payment_method=txn.payment_method,
        transaction_id=txn.transaction_id,
        status=payout_status,
        paid_at=paid_at,
    )


def complete_transaction(
    txn: PaymentTransaction,
    *,
    create_payout: bool = True,
    payout_status: str | None = None,
) -> OwnerPayout | None:
    if txn.status == PaymentTransactionStatus.COMPLETED:
        return OwnerPayout.objects.filter(payment_transaction=txn).first()

    txn.status = PaymentTransactionStatus.COMPLETED
    txn.completed_at = timezone.now()
    txn.save(update_fields=['status', 'completed_at', 'updated_at'])

    bill = txn.bill
    mark_bill_paid(bill)

    if create_payout:
        return create_owner_payout(txn=txn, bill=bill, payout_status=payout_status)
    return None
