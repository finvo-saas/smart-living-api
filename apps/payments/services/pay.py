"""Pay-bill flow — create transaction and invoke gateway."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.models import Bill, BillStatus
from core.exceptions import ForbiddenError, InvalidAccountError, InvalidError, NotFoundError
from payments.gateways.registry import get_gateway
from payments.models import PaymentMethod, PaymentTransaction, PaymentTransactionStatus
from payments.services.helpers import complete_transaction


def _get_bill_for_user(user, bill_id) -> Bill:
    try:
        bill = Bill.objects.get(pk=bill_id, is_deleted=False)
    except Bill.DoesNotExist as exc:
        raise NotFoundError('Bill not found.') from exc

    if bill.owner_id != user.id and user.role != 'admin':
        if bill.tenant_id != user.id:
            raise ForbiddenError('You cannot pay this bill.')
    return bill


def _validate_account(method: str, account_number: str | None) -> None:
    if method in (PaymentMethod.CASH, PaymentMethod.CARD):
        return
    digits = ''.join(c for c in (account_number or '') if c.isdigit())
    if len(digits) < 11:
        raise InvalidAccountError('Enter a valid wallet / account number.')


@transaction.atomic
def pay_bill(user, data: dict) -> PaymentTransaction:
    bill_id = data.get('billId') or data.get('bill_id')
    payment_method = data.get('paymentMethod') or data.get('payment_method')
    amount = Decimal(str(data.get('amount', 0)))
    account_number = (data.get('accountNumber') or data.get('account_number') or '').strip()
    idempotency_key = (data.get('idempotencyKey') or data.get('idempotency_key') or '').strip()

    if not bill_id:
        raise InvalidError('billId is required.')
    if amount <= 0:
        raise InvalidError('Invalid bill payment.')
    if not payment_method:
        raise InvalidError('paymentMethod is required.')

    _validate_account(payment_method, account_number)

    if idempotency_key:
        existing = PaymentTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    bill = _get_bill_for_user(user, bill_id)
    if bill.status == BillStatus.PAID:
        raise InvalidError('Bill is already paid.')

    bill_name = data.get('billName') or data.get('bill_name') or f'{bill.month} {bill.year} — {bill.property_name}'
    property_name = data.get('propertyName') or data.get('property_name') or bill.property_name
    tenant_name = data.get('tenantName') or data.get('tenant_name') or bill.tenant_name

    gateway = get_gateway(payment_method)
    placeholder_txn_id = f'PENDING-{uuid.uuid4().hex[:12]}'

    txn = PaymentTransaction.objects.create(
        user=user,
        bill=bill,
        bill_name=bill_name,
        property_name=property_name,
        tenant_name=tenant_name,
        amount=amount,
        payment_method=payment_method,
        account_number=account_number,
        transaction_id=placeholder_txn_id,
        status=PaymentTransactionStatus.PROCESSING,
        idempotency_key=idempotency_key or None,
    )

    intent = gateway.create_payment(
        amount=amount,
        transaction_id=str(txn.id),
        account_number=account_number,
        metadata={'bill_id': str(bill.id), 'user_id': str(user.id)},
    )

    txn.transaction_id = intent.gateway_txn_id
    txn.gateway_payload = intent.raw
    txn.status = intent.status
    if intent.status == PaymentTransactionStatus.COMPLETED:
        txn.completed_at = timezone.now()
    txn.save(update_fields=[
        'transaction_id',
        'gateway_payload',
        'status',
        'completed_at',
        'updated_at',
    ])

    if intent.status == PaymentTransactionStatus.COMPLETED:
        complete_transaction(txn)

    return txn
