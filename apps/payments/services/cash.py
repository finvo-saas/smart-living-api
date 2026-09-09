"""Owner-recorded received payment (cash / bKash / Nagad) — ledger only by default."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from billing.models import Bill, BillStatus
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from payments.models import PaymentMethod, PaymentTransaction, PaymentTransactionStatus
from payments.services.helpers import bill_paid_total, complete_transaction


def _get_owner_bill(owner, bill_id) -> Bill:
    try:
        bill = Bill.objects.get(pk=bill_id, is_deleted=False)
    except Bill.DoesNotExist as exc:
        raise NotFoundError('Bill not found.') from exc
    if bill.owner_id != owner.id and owner.role != 'admin':
        raise ForbiddenError('Only the bill owner can record payments.')
    return bill


def _normalize_method(raw: str | None) -> str:
    method = (raw or PaymentMethod.CASH).strip()
    allowed = {c.value for c in PaymentMethod}
    if method not in allowed:
        raise InvalidError(f'Unsupported payment method: {method}')
    return method


@transaction.atomic
def record_cash(owner, data: dict) -> tuple[PaymentTransaction, object]:
    """Record money the owner already received (manual BD collection)."""
    bill_id = data.get('billId') or data.get('bill_id')
    amount = Decimal(str(data.get('amount', 0)))
    received_date_raw = data.get('receivedDate') or data.get('received_date')
    payment_method = _normalize_method(
        data.get('paymentMethod') or data.get('payment_method')
    )
    external_trx = (
        data.get('transactionId')
        or data.get('transaction_id')
        or data.get('trxId')
        or ''
    ).strip()

    if not bill_id:
        raise InvalidError('billId is required.')
    if amount <= 0:
        raise InvalidError('Invalid payment amount.')

    bill = _get_owner_bill(owner, bill_id)
    already = bill_paid_total(bill)
    remaining = bill.amount - already
    if remaining <= 0 or bill.status == BillStatus.PAID:
        raise InvalidError('Bill is already paid.')
    if amount > remaining:
        raise InvalidError(f'Amount exceeds remaining due ({remaining}).')

    bill_name = (
        data.get('billName')
        or data.get('bill_name')
        or f'{bill.month} {bill.year} — {bill.property_name}'
    )
    property_name = data.get('propertyName') or data.get('property_name') or bill.property_name
    tenant_name = data.get('tenantName') or data.get('tenant_name') or bill.tenant_name
    receipt_note = data.get('receiptNote') or data.get('receipt_note') or ''
    receipt_file_name = data.get('receiptFileName') or data.get('receipt_file_name') or ''

    completed_at = timezone.now()
    if received_date_raw:
        parsed_dt = parse_datetime(str(received_date_raw))
        if parsed_dt:
            completed_at = (
                parsed_dt if timezone.is_aware(parsed_dt) else timezone.make_aware(parsed_dt)
            )
        else:
            parsed_d = parse_date(str(received_date_raw))
            if parsed_d:
                completed_at = timezone.make_aware(
                    datetime.combine(parsed_d, datetime.min.time())
                )

    if external_trx:
        txn_id = external_trx
        if PaymentTransaction.objects.filter(transaction_id=txn_id).exists():
            txn_id = f'{external_trx}-{uuid.uuid4().hex[:6]}'
    else:
        prefix = {
            PaymentMethod.BKASH: 'BKS',
            PaymentMethod.NAGAD: 'NGD',
            PaymentMethod.ROCKET: 'RKT',
            PaymentMethod.BANK_TRANSFER: 'BNK',
            PaymentMethod.CARD: 'CRD',
        }.get(payment_method, 'CASH')
        txn_id = f'{prefix}-MAN-{uuid.uuid4().hex[:10].upper()}'

    txn = PaymentTransaction.objects.create(
        user=bill.tenant or owner,
        bill=bill,
        bill_name=bill_name,
        property_name=property_name,
        tenant_name=tenant_name,
        amount=amount,
        payment_method=payment_method,
        account_number='',
        transaction_id=txn_id,
        status=PaymentTransactionStatus.COMPLETED,
        receipt_note=receipt_note,
        receipt_file_name=receipt_file_name,
        completed_at=completed_at,
        gateway_payload={
            'manual': True,
            'recordedBy': str(owner.id),
            'receivedBy': data.get('receivedBy') or data.get('received_by') or '',
            'externalTrxId': external_trx,
        },
    )

    # Ledger only — create_payout gated inside complete_transaction / should_create_payout
    payout = complete_transaction(txn)
    return txn, payout
