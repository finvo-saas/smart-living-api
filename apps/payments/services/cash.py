"""Owner-recorded cash payment flow."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from billing.models import Bill, BillStatus
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from payments.models import PaymentMethod, PaymentTransaction, PaymentTransactionStatus, PayoutStatus
from payments.services.helpers import complete_transaction


def _get_owner_bill(owner, bill_id) -> Bill:
    try:
        bill = Bill.objects.get(pk=bill_id, is_deleted=False)
    except Bill.DoesNotExist as exc:
        raise NotFoundError('Bill not found.') from exc
    if bill.owner_id != owner.id and owner.role != 'admin':
        raise ForbiddenError('Only the bill owner can record cash payments.')
    return bill


@transaction.atomic
def record_cash(owner, data: dict) -> tuple[PaymentTransaction, object]:
    bill_id = data.get('billId') or data.get('bill_id')
    amount = Decimal(str(data.get('amount', 0)))
    received_date_raw = data.get('receivedDate') or data.get('received_date')

    if not bill_id:
        raise InvalidError('billId is required.')
    if amount <= 0:
        raise InvalidError('Invalid payment amount.')

    bill = _get_owner_bill(owner, bill_id)
    if bill.status == BillStatus.PAID:
        raise InvalidError('Bill is already paid.')

    bill_name = data.get('billName') or data.get('bill_name') or f'{bill.month} {bill.year} — {bill.property_name}'
    property_name = data.get('propertyName') or data.get('property_name') or bill.property_name
    tenant_name = data.get('tenantName') or data.get('tenant_name') or bill.tenant_name
    receipt_note = data.get('receiptNote') or data.get('receipt_note') or ''
    receipt_file_name = data.get('receiptFileName') or data.get('receipt_file_name') or ''

    completed_at = timezone.now()
    if received_date_raw:
        parsed_dt = parse_datetime(received_date_raw)
        if parsed_dt:
            completed_at = parsed_dt if timezone.is_aware(parsed_dt) else timezone.make_aware(parsed_dt)
        else:
            parsed_d = parse_date(received_date_raw)
            if parsed_d:
                completed_at = timezone.make_aware(datetime.combine(parsed_d, datetime.min.time()))

    from payments.gateways.cash import CashGateway

    gateway = CashGateway()
    intent = gateway.create_payment(amount=amount, transaction_id=str(bill_id))

    txn = PaymentTransaction.objects.create(
        user=bill.tenant or owner,
        bill=bill,
        bill_name=bill_name,
        property_name=property_name,
        tenant_name=tenant_name,
        amount=amount,
        payment_method=PaymentMethod.CASH,
        account_number='',
        transaction_id=intent.gateway_txn_id,
        status=PaymentTransactionStatus.COMPLETED,
        receipt_note=receipt_note,
        receipt_file_name=receipt_file_name,
        completed_at=completed_at,
        gateway_payload=intent.raw,
    )

    payout = complete_transaction(txn, payout_status=PayoutStatus.PAID)
    return txn, payout
