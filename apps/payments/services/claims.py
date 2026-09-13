"""Tenant/member “I paid” claims — owner confirms into ledger."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.models import Bill, BillStatus
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from mess.models import DepositStatus, MemberDeposit, Mess, MessStudent
from payments.models import (
    PaymentClaim,
    PaymentClaimStatus,
    PaymentMethod,
    PaymentTransaction,
    PaymentTransactionStatus,
)
from payments.services.cash import record_cash
from payments.services.collection import models_q_owner
from payments.services.helpers import bill_paid_total


def _normalize_method(raw: str | None) -> str:
    method = (raw or PaymentMethod.BKASH).strip()
    allowed = {c.value for c in PaymentMethod}
    if method not in allowed:
        raise InvalidError(f'Unsupported payment method: {method}')
    if method == PaymentMethod.CARD:
        raise InvalidError('Use bKash, Nagad, Rocket, bank transfer, or cash for claims.')
    return method


def serialize_claim(claim: PaymentClaim) -> dict:
    return {
        'id': str(claim.id),
        'billId': str(claim.bill_id) if claim.bill_id else None,
        'messId': str(claim.mess_id) if claim.mess_id else None,
        'studentId': str(claim.student_id) if claim.student_id else None,
        'claimedById': str(claim.claimed_by_id),
        'amount': float(claim.amount),
        'paymentMethod': claim.payment_method,
        'transactionId': claim.transaction_id or '',
        'note': claim.note or '',
        'status': claim.status,
        'rejectionReason': claim.rejection_reason or '',
        'reviewedAt': claim.reviewed_at.isoformat() if claim.reviewed_at else None,
        'createdAt': claim.created_at.isoformat() if claim.created_at else None,
        'billName': (
            f'{claim.bill.month} {claim.bill.year} — {claim.bill.property_name}'
            if claim.bill_id
            else None
        ),
        'tenantName': claim.bill.tenant_name if claim.bill_id else (
            claim.student.name if claim.student_id else ''
        ),
        'propertyName': (
            claim.bill.property_name
            if claim.bill_id
            else (claim.mess.name if claim.mess_id else '')
        ),
    }


@transaction.atomic
def create_bill_claim(user, data: dict) -> PaymentClaim:
    bill_id = data.get('billId') or data.get('bill_id')
    amount = Decimal(str(data.get('amount', 0)))
    method = _normalize_method(data.get('paymentMethod') or data.get('payment_method'))
    trx = (data.get('transactionId') or data.get('transaction_id') or '').strip()
    note = (data.get('note') or '').strip()

    if not bill_id:
        raise InvalidError('billId is required.')
    if amount <= 0:
        raise InvalidError('Invalid amount.')
    if method != PaymentMethod.CASH and not trx:
        raise InvalidError('transactionId is required for digital payments.')

    try:
        bill = Bill.objects.select_related('owner').get(pk=bill_id, is_deleted=False)
    except Bill.DoesNotExist as exc:
        raise NotFoundError('Bill not found.') from exc

    if bill.tenant_id != user.id and user.role != 'admin':
        raise ForbiddenError('Only the tenant can claim payment on this bill.')
    if bill.status == BillStatus.PAID:
        raise InvalidError('Bill is already paid.')

    remaining = bill.amount - bill_paid_total(bill)
    if amount > remaining:
        raise InvalidError(f'Amount exceeds remaining due ({remaining}).')

    pending = PaymentClaim.objects.filter(
        bill=bill,
        claimed_by=user,
        status=PaymentClaimStatus.PENDING,
    ).exists()
    if pending:
        raise InvalidError('You already have a pending claim for this bill.')

    claim = PaymentClaim.objects.create(
        bill=bill,
        claimed_by=user,
        amount=amount,
        payment_method=method,
        transaction_id=trx,
        note=note,
        status=PaymentClaimStatus.PENDING,
    )
    from billing.notify import schedule_payment_claim

    schedule_payment_claim(claim.id)
    return claim


@transaction.atomic
def create_mess_claim(user, data: dict) -> PaymentClaim:
    mess_id = data.get('messId') or data.get('mess_id')
    student_id = data.get('studentId') or data.get('student_id')
    amount = Decimal(str(data.get('amount', 0)))
    method = _normalize_method(data.get('paymentMethod') or data.get('payment_method'))
    trx = (data.get('transactionId') or data.get('transaction_id') or '').strip()
    note = (data.get('note') or '').strip()
    day_raw = data.get('date')

    if not mess_id:
        raise InvalidError('messId is required.')
    if amount <= 0:
        raise InvalidError('Invalid amount.')
    if method != PaymentMethod.CASH and not trx:
        raise InvalidError('transactionId is required for digital payments.')

    try:
        mess = Mess.objects.get(pk=mess_id, is_deleted=False)
    except Mess.DoesNotExist as exc:
        raise NotFoundError('Mess not found.') from exc

    student = None
    if student_id:
        try:
            student = MessStudent.objects.get(pk=student_id, mess=mess, is_deleted=False)
        except MessStudent.DoesNotExist as exc:
            raise NotFoundError('Member not found.') from exc
    else:
        student = MessStudent.objects.filter(
            mess=mess, user=user, is_deleted=False
        ).first()
        if student is None:
            raise ForbiddenError('You are not a member of this mess.')

    if student.user_id != user.id and user.role != 'admin':
        raise ForbiddenError('You can only claim for your own membership.')

    from datetime import date as date_cls

    from django.utils.dateparse import parse_date

    day = parse_date(str(day_raw)) if day_raw else timezone.localdate()
    if day is None:
        day = timezone.localdate()

    claim = PaymentClaim.objects.create(
        mess=mess,
        student=student,
        claimed_by=user,
        amount=amount,
        payment_method=method,
        transaction_id=trx,
        note=note,
        status=PaymentClaimStatus.PENDING,
    )

    deposit = MemberDeposit.objects.create(
        mess=mess,
        student=student,
        amount=amount,
        date=day if isinstance(day, date_cls) else timezone.localdate(),
        note=note or 'Member payment claim',
        payment_method=method,
        transaction_id=trx,
        status=DepositStatus.PENDING_CLAIM,
        claimed_by=user,
        created_by=user,
    )
    claim.member_deposit = deposit
    claim.save(update_fields=['member_deposit', 'updated_at'])
    from billing.notify import schedule_payment_claim

    schedule_payment_claim(claim.id)
    return claim


def list_claims_for_owner(owner, *, status: str | None = None) -> list[dict]:
    qs = (
        PaymentClaim.objects.filter(models_q_owner(owner))
        .select_related('bill', 'mess', 'student', 'claimed_by')
        .order_by('-created_at')
    )
    if status:
        qs = qs.filter(status=status)
    return [serialize_claim(c) for c in qs[:200]]


def list_claims_for_user(user) -> list[dict]:
    qs = (
        PaymentClaim.objects.filter(claimed_by=user)
        .select_related('bill', 'mess', 'student')
        .order_by('-created_at')
    )
    return [serialize_claim(c) for c in qs[:100]]


@transaction.atomic
def review_claim(owner, claim_id, *, approve: bool, reason: str = '') -> PaymentClaim:
    try:
        claim = PaymentClaim.objects.select_related(
            'bill',
            'mess',
            'student',
            'member_deposit',
            'payment_transaction',
        ).get(pk=claim_id)
    except PaymentClaim.DoesNotExist as exc:
        raise NotFoundError('Claim not found.') from exc

    is_owner = False
    if claim.bill_id and (claim.bill.owner_id == owner.id or owner.role == 'admin'):
        is_owner = True
    if claim.mess_id and (claim.mess.owner_id == owner.id or owner.role == 'admin'):
        is_owner = True
    if not is_owner:
        raise ForbiddenError('You cannot review this claim.')

    if claim.status != PaymentClaimStatus.PENDING:
        raise InvalidError('Claim is already reviewed.')

    claim.reviewed_by = owner
    claim.reviewed_at = timezone.now()

    if not approve:
        claim.status = PaymentClaimStatus.REJECTED
        claim.rejection_reason = reason or 'Rejected by owner'
        claim.save()
        if claim.member_deposit_id:
            dep = claim.member_deposit
            dep.status = DepositStatus.REJECTED
            dep.save(update_fields=['status', 'updated_at'])
        pending_txn = claim.payment_transaction
        if (
            pending_txn
            and pending_txn.status == PaymentTransactionStatus.PENDING
        ):
            pending_txn.status = PaymentTransactionStatus.FAILED
            pending_txn.failure_reason = claim.rejection_reason
            pending_txn.save(
                update_fields=['status', 'failure_reason', 'updated_at'],
            )
        from billing.notify import schedule_payment_claim

        schedule_payment_claim(claim.id, rejected=True, reason=claim.rejection_reason)
        return claim

    claim.status = PaymentClaimStatus.CONFIRMED
    claim.save()

    if claim.bill_id:
        pending_txn = claim.payment_transaction
        if (
            pending_txn
            and pending_txn.status == PaymentTransactionStatus.PENDING
        ):
            if claim.note:
                pending_txn.receipt_note = claim.note
                pending_txn.save(update_fields=['receipt_note', 'updated_at'])
            from payments.services.helpers import complete_transaction

            complete_transaction(pending_txn)
        else:
            txn, _ = record_cash(
                owner,
                {
                    'billId': claim.bill_id,
                    'amount': claim.amount,
                    'paymentMethod': claim.payment_method,
                    'transactionId': claim.transaction_id,
                    'receivedDate': timezone.localdate().isoformat(),
                    'receiptNote': claim.note or 'Confirmed payment claim',
                    'tenantName': claim.bill.tenant_name,
                    'propertyName': claim.bill.property_name,
                },
            )
            claim.payment_transaction = txn
            claim.save(update_fields=['payment_transaction', 'updated_at'])
    elif claim.member_deposit_id:
        dep = claim.member_deposit
        dep.status = DepositStatus.CONFIRMED
        dep.confirmed_by = owner
        dep.payment_method = claim.payment_method
        dep.transaction_id = claim.transaction_id
        dep.save(
            update_fields=[
                'status',
                'confirmed_by',
                'payment_method',
                'transaction_id',
                'updated_at',
            ]
        )

    if claim.mess_id and not claim.bill_id:
        from billing.notify import schedule_claim_confirmed

        schedule_claim_confirmed(claim.id)
    return claim
