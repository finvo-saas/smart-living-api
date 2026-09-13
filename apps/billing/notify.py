"""Bill and payment alerts for the renter and owner."""
from __future__ import annotations

import logging

from django.db import transaction

from messaging.models import NotificationType

logger = logging.getLogger(__name__)

BILLS_URL = '/bills'
PAYMENTS_URL = '/payments'


def schedule_bill_issued(bill_id) -> None:
    transaction.on_commit(lambda bid=bill_id: notify_bill_issued(bid))


def notify_bill_issued(bill_id) -> None:
    bill = _load_bill(bill_id)
    if bill is None or bill.tenant_id is None:
        return
    place = _place(bill)
    _send(
        bill.tenant,
        title='New bill',
        body=(
            f'{place}: ৳{_money(bill.amount)} is due '
            f'{bill.due_date.isoformat()} ({bill.month} {bill.year}).'
        ),
        url=BILLS_URL,
        tag=f'bill-issued-{bill.id}',
    )


def notify_bills_overdue(bill_ids) -> None:
    from billing.models import Bill

    bills = Bill.objects.filter(
        pk__in=list(bill_ids),
        is_deleted=False,
        tenant__isnull=False,
    ).select_related('tenant')
    for bill in bills:
        place = _place(bill)
        _send(
            bill.tenant,
            title='Bill overdue',
            body=f'{place}: ৳{_money(bill.amount)} was due {bill.due_date.isoformat()}.',
            url=f'{BILLS_URL}?status=overdue',
            tag=f'bill-overdue-{bill.id}',
        )


def schedule_payment_received(txn_id) -> None:
    transaction.on_commit(lambda tid=txn_id: notify_payment_received(tid))


def notify_payment_received(txn_id) -> None:
    from payments.models import PaymentTransaction

    txn = (
        PaymentTransaction.objects.filter(pk=txn_id)
        .select_related('user', 'bill', 'bill__owner', 'bill__tenant')
        .first()
    )
    if txn is None or txn.bill_id is None:
        return
    bill = txn.bill
    place = _place(bill)
    amount = _money(txn.amount)
    payer = txn.tenant_name or (txn.user.name if txn.user_id else 'A renter')
    if bill.owner_id and bill.owner_id != txn.user_id:
        _send(
            bill.owner,
            title='Payment received',
            body=f'{payer} paid ৳{amount} for {place}.',
            url=PAYMENTS_URL,
            tag=f'payment-owner-{txn.id}',
        )
    if txn.user_id and txn.user_id != bill.owner_id:
        _send(
            txn.user,
            title='Payment confirmed',
            body=f'Your payment of ৳{amount} for {place} is confirmed.',
            url=BILLS_URL,
            tag=f'payment-renter-{txn.id}',
        )


def schedule_claim_confirmed(claim_id) -> None:
    transaction.on_commit(lambda cid=claim_id: notify_claim_confirmed(cid))


def notify_claim_confirmed(claim_id) -> None:
    from payments.models import PaymentClaim

    claim = (
        PaymentClaim.objects.filter(pk=claim_id)
        .select_related('claimed_by', 'mess')
        .first()
    )
    if claim is None or not claim.claimed_by_id:
        return
    place = claim.mess.name if claim.mess_id else 'your payment'
    _send(
        claim.claimed_by,
        title='Payment confirmed',
        body=f'Your payment of ৳{_money(claim.amount)} for {place} was confirmed.',
        url=PAYMENTS_URL,
        tag=f'claim-confirmed-{claim.id}',
    )


def schedule_payment_claim(claim_id, *, rejected: bool = False, reason: str = '') -> None:
    transaction.on_commit(
        lambda cid=claim_id, rej=rejected, why=reason: notify_payment_claim(
            cid,
            rejected=rej,
            reason=why,
        ),
    )


def notify_payment_claim(claim_id, *, rejected: bool = False, reason: str = '') -> None:
    from payments.models import PaymentClaim

    claim = (
        PaymentClaim.objects.filter(pk=claim_id)
        .select_related('bill', 'bill__owner', 'claimed_by', 'mess', 'mess__owner')
        .first()
    )
    if claim is None:
        return
    amount = _money(claim.amount)
    if rejected:
        why = (reason or claim.rejection_reason or '').strip()
        body = f'Your payment claim of ৳{amount} was declined.'
        if why:
            body = f'{body} Reason: {why}'
        _send(
            claim.claimed_by,
            title='Payment not confirmed',
            body=body,
            url=BILLS_URL,
            tag=f'claim-rejected-{claim.id}',
        )
        return

    owner = None
    place = 'a bill'
    if claim.bill_id:
        owner = claim.bill.owner
        place = _place(claim.bill)
    elif claim.mess_id:
        owner = claim.mess.owner
        place = claim.mess.name
    who = claim.claimed_by.name if claim.claimed_by_id else 'A renter'
    _send(
        owner,
        title='Payment to confirm',
        body=f'{who} submitted ৳{amount} for {place}. Confirm it in payments.',
        url=PAYMENTS_URL,
        tag=f'claim-pending-{claim.id}',
        skip_ids={claim.claimed_by_id},
    )


def _load_bill(bill_id):
    from billing.models import Bill

    return (
        Bill.objects.filter(pk=bill_id, is_deleted=False)
        .select_related('tenant')
        .first()
    )


def _place(bill) -> str:
    bits = [bill.property_name or '']
    if bill.flat_number:
        bits.append(f'Flat {bill.flat_number}')
    elif bill.seat_number:
        bits.append(f'Seat {bill.seat_number}')
    return ' · '.join(bit for bit in bits if bit) or 'your bill'


def _money(amount) -> str:
    try:
        return f'{float(amount):,.0f}'
    except (TypeError, ValueError):
        return '0'


def _send(user, *, title: str, body: str, url: str, tag: str, skip_ids=None) -> None:
    from accounts.services.email import notify_channels

    if user is None or not getattr(user, 'id', None):
        return
    skip = {str(item) for item in (skip_ids or set()) if item}
    if str(user.id) in skip:
        return
    try:
        notify_channels(
            user,
            title=title[:255],
            body=body,
            url=url,
            ntype=NotificationType.BILL,
            tag=tag,
        )
    except Exception:
        logger.exception('Bill notice failed tag=%s user=%s', tag, user.id)
