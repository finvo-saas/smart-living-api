"""Shared payment completion helpers."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from billing.models import Bill, BillStatus
from payments.models import (
    CollectionMode,
    OwnerCollectionSettings,
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


def get_or_create_collection_settings(owner) -> OwnerCollectionSettings:
    settings_obj, _ = OwnerCollectionSettings.objects.get_or_create(owner=owner)
    return settings_obj


def should_create_payout(owner) -> bool:
    """Platform payout/commission only for opt-in managed collect."""
    if owner is None:
        return False
    cfg = getattr(owner, 'collection_settings', None)
    if cfg is None:
        try:
            cfg = OwnerCollectionSettings.objects.filter(owner=owner).first()
        except Exception:
            return False
    if cfg is None:
        return False
    return (
        cfg.collection_mode == CollectionMode.PLATFORM_COLLECT
        and cfg.platform_collect_enabled
    )


def bill_paid_total(bill: Bill) -> Decimal:
    total = (
        PaymentTransaction.objects.filter(
            bill=bill,
            status=PaymentTransactionStatus.COMPLETED,
        ).aggregate(t=Sum('amount'))['t']
        or Decimal('0')
    )
    return Decimal(str(total))


def sync_bill_payment_state(bill: Bill | None) -> None:
    """Update amount_paid / status from completed ledger transactions."""
    if bill is None:
        return
    paid = bill_paid_total(bill)
    bill.amount_paid = paid
    fields = ['amount_paid', 'updated_at']
    if paid >= bill.amount and bill.amount > 0:
        if bill.status != BillStatus.PAID:
            bill.status = BillStatus.PAID
            bill.paid_date = timezone.now().date()
            fields.extend(['status', 'paid_date'])
    elif paid > 0 and bill.status == BillStatus.PAID:
        # Partial after previous full mark — reopen as unpaid
        bill.status = BillStatus.UNPAID
        bill.paid_date = None
        fields.extend(['status', 'paid_date'])
    bill.save(update_fields=fields)


def mark_bill_paid(bill: Bill | None) -> None:
    if bill is None:
        return
    sync_bill_payment_state(bill)
    if bill.status == BillStatus.PAID:
        return
    # Force-complete when caller intends full settlement without partial math
    bill.status = BillStatus.PAID
    bill.paid_date = timezone.now().date()
    bill.amount_paid = bill.amount
    bill.save(update_fields=['status', 'paid_date', 'amount_paid', 'updated_at'])


def create_owner_payout(
    *,
    txn: PaymentTransaction,
    bill: Bill | None,
    payout_status: str | None = None,
) -> OwnerPayout | None:
    if bill is None:
        return None
    if not should_create_payout(bill.owner):
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
    create_payout: bool | None = None,
    payout_status: str | None = None,
    force_mark_bill_paid: bool = False,
) -> OwnerPayout | None:
    if txn.status == PaymentTransactionStatus.COMPLETED:
        return OwnerPayout.objects.filter(payment_transaction=txn).first()

    txn.status = PaymentTransactionStatus.COMPLETED
    txn.completed_at = timezone.now()
    txn.save(update_fields=['status', 'completed_at', 'updated_at'])

    bill = txn.bill
    if force_mark_bill_paid:
        mark_bill_paid(bill)
    else:
        sync_bill_payment_state(bill)

    try:
        from documents.services.receipts import issue_rent_receipt_for_transaction

        issue_rent_receipt_for_transaction(txn)
    except Exception:
        pass

    if create_payout is None:
        create_payout = should_create_payout(bill.owner) if bill else False

    if create_payout:
        return create_owner_payout(txn=txn, bill=bill, payout_status=payout_status)
    return None
