"""Pay-bill flow — create transaction and invoke gateway."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.models import Bill, BillStatus
from core.exceptions import ForbiddenError, InvalidAccountError, InvalidError, NotFoundError
from payments.gateways.registry import get_gateway
from payments.models import (
    CollectionMode,
    OwnerGatewayCredential,
    PaymentGateway,
    PaymentMethod,
    PaymentTransaction,
    PaymentTransactionStatus,
)
from payments.services.helpers import (
    bill_paid_total,
    complete_transaction,
    get_or_create_collection_settings,
    should_create_payout,
)


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


def _pay_bill_cash(
    user,
    bill: Bill,
    *,
    amount: Decimal,
    bill_name: str,
    property_name: str,
    tenant_name: str,
    idempotency_key: str,
    note: str = '',
) -> PaymentTransaction:
    """
    Cash is never auto-completed: create an “I paid” claim + pending txn.
    Owner confirms on Payments → Claims (or Record cash on Bills).
    """
    from payments.services.claims import create_bill_claim

    remaining = bill.amount - bill_paid_total(bill)
    if remaining <= 0:
        raise InvalidError('Bill is already paid.')
    claim_amount = amount if amount <= remaining else remaining

    claim = create_bill_claim(
        user,
        {
            'billId': bill.id,
            'amount': claim_amount,
            'paymentMethod': PaymentMethod.CASH,
            'note': note
            or 'Cash payment — awaiting owner confirmation of receipt',
        },
    )

    txn_id = f'CASH-CLAIM-{str(claim.id).replace("-", "")[:12].upper()}'
    txn = PaymentTransaction.objects.create(
        user=user,
        bill=bill,
        bill_name=bill_name,
        property_name=property_name,
        tenant_name=tenant_name,
        amount=claim_amount,
        payment_method=PaymentMethod.CASH,
        account_number='',
        transaction_id=txn_id,
        status=PaymentTransactionStatus.PENDING,
        idempotency_key=idempotency_key or None,
        gateway_payload={
            'claimId': str(claim.id),
            'awaitingOwnerConfirm': True,
            'manualCash': True,
        },
    )
    claim.payment_transaction = txn
    claim.save(update_fields=['payment_transaction', 'updated_at'])
    return txn


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

    bill_name = (
        data.get('billName')
        or data.get('bill_name')
        or f'{bill.month} {bill.year} — {bill.property_name}'
    )
    property_name = data.get('propertyName') or data.get('property_name') or bill.property_name
    tenant_name = data.get('tenantName') or data.get('tenant_name') or bill.tenant_name

    if payment_method == PaymentMethod.CASH:
        return _pay_bill_cash(
            user,
            bill,
            amount=amount,
            bill_name=bill_name,
            property_name=property_name,
            tenant_name=tenant_name,
            idempotency_key=idempotency_key,
            note=(data.get('note') or '').strip(),
        )

    cfg = get_or_create_collection_settings(bill.owner)
    # Manual mode: digital methods use “I paid” claims, not platform gateway checkout.
    if cfg.collection_mode == CollectionMode.MANUAL and not should_create_payout(bill.owner):
        raise InvalidError(
            'Owner collects manually. Use “I paid” with your TrxID, or ask the owner '
            'to enable their merchant gateway.'
        )

    owner_cred = None
    method_to_gateway = {
        PaymentMethod.BKASH: PaymentGateway.BKASH,
        PaymentMethod.NAGAD: PaymentGateway.NAGAD,
        PaymentMethod.ROCKET: PaymentGateway.ROCKET,
    }
    gw_key = method_to_gateway.get(payment_method)
    if gw_key and cfg.collection_mode == CollectionMode.OWNER_GATEWAY:
        owner_cred = OwnerGatewayCredential.objects.filter(
            owner=bill.owner,
            gateway=gw_key,
            is_active=True,
        ).first()
        if owner_cred is None:
            raise InvalidError(
                'Owner has not connected this payment method yet. '
                'Pay via their wallet number and submit an “I paid” claim.'
            )

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
        gateway_payload={
            'ownerGateway': bool(owner_cred),
            'ownerGatewayId': str(owner_cred.id) if owner_cred else None,
            'collectionMode': cfg.collection_mode,
        },
    )

    metadata = {
        'bill_id': str(bill.id),
        'user_id': str(user.id),
        'owner_id': str(bill.owner_id),
        'collection_mode': cfg.collection_mode,
    }
    if owner_cred:
        metadata['owner_merchant'] = owner_cred.merchant_number
        metadata['owner_credential_id'] = str(owner_cred.id)
        # Pass owner secrets into gateway layer (live wire-up uses these later)
        metadata['owner_credentials'] = owner_cred.credentials or {}

    intent = gateway.create_payment(
        amount=amount,
        transaction_id=str(txn.id),
        account_number=account_number,
        metadata=metadata,
    )

    payload = dict(txn.gateway_payload or {})
    payload.update(intent.raw or {})
    txn.transaction_id = intent.gateway_txn_id
    txn.gateway_payload = payload
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
