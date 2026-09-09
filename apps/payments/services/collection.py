"""Owner collection settings, instructions, ledger analytics, and reports."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from billing.models import Bill, BillStatus
from core.exceptions import ForbiddenError, InvalidError
from mess.models import DepositStatus, MemberDeposit
from payments.models import (
    CollectionMode,
    OwnerGatewayCredential,
    PaymentClaim,
    PaymentClaimStatus,
    PaymentGateway,
    PaymentMethod,
    PaymentTransaction,
    PaymentTransactionStatus,
)
from payments.services.helpers import get_or_create_collection_settings
from payments.services.payouts import owner_analytics as payout_analytics


INSTRUCTION_FIELDS = (
    'bkash_number',
    'nagad_number',
    'rocket_number',
    'bank_name',
    'bank_account_number',
    'bank_account_name',
    'payment_note',
)


def serialize_instructions(cfg) -> dict:
    return {
        'bkashNumber': cfg.bkash_number or '',
        'nagadNumber': cfg.nagad_number or '',
        'rocketNumber': cfg.rocket_number or '',
        'bankName': cfg.bank_name or '',
        'bankAccountNumber': cfg.bank_account_number or '',
        'bankAccountName': cfg.bank_account_name or '',
        'paymentNote': cfg.payment_note or '',
    }


def serialize_collection_settings(cfg) -> dict:
    return {
        'collectionMode': cfg.collection_mode,
        'platformCollectEnabled': cfg.platform_collect_enabled,
        'instructions': serialize_instructions(cfg),
        'showsPlatformPayouts': (
            cfg.collection_mode == CollectionMode.PLATFORM_COLLECT
            and cfg.platform_collect_enabled
        ),
    }


def get_collection_settings(owner) -> dict:
    return serialize_collection_settings(get_or_create_collection_settings(owner))


def update_collection_settings(owner, data: dict) -> dict:
    cfg = get_or_create_collection_settings(owner)
    mode = data.get('collectionMode') or data.get('collection_mode')
    if mode:
        allowed = {c.value for c in CollectionMode}
        if mode not in allowed:
            raise InvalidError('Invalid collectionMode.')
        if mode == CollectionMode.PLATFORM_COLLECT and not (
            data.get('platformCollectEnabled', data.get('platform_collect_enabled', False))
            or cfg.platform_collect_enabled
        ):
            # Require explicit opt-in flag when switching to platform collect
            flag = data.get('platformCollectEnabled')
            if flag is None:
                flag = data.get('platform_collect_enabled')
            if not flag:
                raise InvalidError(
                    'platformCollectEnabled must be true to use platform collect.'
                )
        cfg.collection_mode = mode

    if 'platformCollectEnabled' in data or 'platform_collect_enabled' in data:
        cfg.platform_collect_enabled = bool(
            data.get('platformCollectEnabled', data.get('platform_collect_enabled'))
        )
        if not cfg.platform_collect_enabled and cfg.collection_mode == CollectionMode.PLATFORM_COLLECT:
            cfg.collection_mode = CollectionMode.MANUAL

    instructions = data.get('instructions') if isinstance(data.get('instructions'), dict) else data
    mapping = {
        'bkashNumber': 'bkash_number',
        'nagadNumber': 'nagad_number',
        'rocketNumber': 'rocket_number',
        'bankName': 'bank_name',
        'bankAccountNumber': 'bank_account_number',
        'bankAccountName': 'bank_account_name',
        'paymentNote': 'payment_note',
        'bkash_number': 'bkash_number',
        'nagad_number': 'nagad_number',
        'rocket_number': 'rocket_number',
        'bank_name': 'bank_name',
        'bank_account_number': 'bank_account_number',
        'bank_account_name': 'bank_account_name',
        'payment_note': 'payment_note',
    }
    for src, dest in mapping.items():
        if src in instructions and instructions[src] is not None:
            setattr(cfg, dest, str(instructions[src]).strip())

    cfg.save()
    return serialize_collection_settings(cfg)


def resolve_payment_instructions(*, owner, mess=None) -> dict:
    """Mess-level numbers override owner defaults when present."""
    cfg = get_or_create_collection_settings(owner)
    base = serialize_instructions(cfg)
    if mess is None:
        return {
            **base,
            'collectionMode': cfg.collection_mode,
            'hasOwnerGateway': OwnerGatewayCredential.objects.filter(
                owner=owner, is_active=True
            ).exists(),
        }

    overrides = {
        'bkashNumber': mess.bkash_number or base['bkashNumber'],
        'nagadNumber': mess.nagad_number or base['nagadNumber'],
        'rocketNumber': mess.rocket_number or base['rocketNumber'],
        'bankName': mess.bank_name or base['bankName'],
        'bankAccountNumber': mess.bank_account_number or base['bankAccountNumber'],
        'bankAccountName': mess.bank_account_name or base['bankAccountName'],
        'paymentNote': mess.payment_note or base['paymentNote'],
    }
    return {
        **overrides,
        'collectionMode': cfg.collection_mode,
        'hasOwnerGateway': OwnerGatewayCredential.objects.filter(
            owner=owner, is_active=True
        ).exists(),
    }


def serialize_gateway_credential(cred: OwnerGatewayCredential) -> dict:
    keys = list((cred.credentials or {}).keys())
    return {
        'id': str(cred.id),
        'gateway': cred.gateway,
        'displayName': cred.display_name or '',
        'merchantNumber': cred.merchant_number or '',
        'isActive': cred.is_active,
        'isSandbox': cred.is_sandbox,
        'credentialKeys': keys,
        'hasCredentials': bool(keys),
        'updatedAt': cred.updated_at.isoformat() if cred.updated_at else None,
    }


def upsert_gateway_credential(owner, data: dict) -> dict:
    gateway = (data.get('gateway') or '').strip().lower()
    allowed = {c.value for c in PaymentGateway}
    if gateway not in allowed:
        raise InvalidError('gateway must be bkash, nagad, or rocket.')

    cred, _ = OwnerGatewayCredential.objects.get_or_create(
        owner=owner,
        gateway=gateway,
        defaults={'is_sandbox': True},
    )
    if 'displayName' in data or 'display_name' in data:
        cred.display_name = str(data.get('displayName') or data.get('display_name') or '').strip()
    if 'merchantNumber' in data or 'merchant_number' in data:
        cred.merchant_number = str(
            data.get('merchantNumber') or data.get('merchant_number') or ''
        ).strip()
    if 'isActive' in data or 'is_active' in data:
        cred.is_active = bool(data.get('isActive', data.get('is_active')))
    if 'isSandbox' in data or 'is_sandbox' in data:
        cred.is_sandbox = bool(data.get('isSandbox', data.get('is_sandbox')))
    raw_creds = data.get('credentials')
    if isinstance(raw_creds, dict) and raw_creds:
        merged = dict(cred.credentials or {})
        merged.update({str(k): str(v) for k, v in raw_creds.items() if v is not None})
        cred.credentials = merged
    cred.save()

    # Switching to owner gateway when first credential is saved
    cfg = get_or_create_collection_settings(owner)
    if cred.is_active and cfg.collection_mode == CollectionMode.MANUAL:
        cfg.collection_mode = CollectionMode.OWNER_GATEWAY
        cfg.save(update_fields=['collection_mode', 'updated_at'])

    return serialize_gateway_credential(cred)


def list_gateway_credentials(owner) -> list[dict]:
    qs = OwnerGatewayCredential.objects.filter(owner=owner)
    return [serialize_gateway_credential(c) for c in qs]


def collection_ledger_analytics(owner) -> dict:
    """Money marked received by the owner — not platform settlement."""
    bill_ids = Bill.objects.filter(owner=owner, is_deleted=False).values_list('id', flat=True)
    qs = PaymentTransaction.objects.filter(
        bill_id__in=bill_ids,
        status=PaymentTransactionStatus.COMPLETED,
    )

    totals = qs.aggregate(total=Sum('amount'), count=Count('id'))
    by_method = (
        qs.values('payment_method')
        .annotate(amount=Sum('amount'), count=Count('id'))
        .order_by('-amount')
    )
    monthly: dict[str, Decimal] = defaultdict(lambda: Decimal('0'))
    for txn in qs.filter(completed_at__isnull=False).iterator():
        key = txn.completed_at.strftime('%Y-%m')
        monthly[key] += txn.amount

    unpaid = Bill.objects.filter(
        owner=owner,
        is_deleted=False,
        status__in=[BillStatus.UNPAID, BillStatus.OVERDUE],
    )
    outstanding = Decimal('0')
    for bill in unpaid.only('amount', 'amount_paid'):
        remaining = bill.amount - (bill.amount_paid or Decimal('0'))
        if remaining > 0:
            outstanding += remaining

    mess_received = (
        MemberDeposit.objects.filter(
            mess__owner=owner,
            is_deleted=False,
            status=DepositStatus.CONFIRMED,
        ).aggregate(t=Sum('amount'))['t']
        or Decimal('0')
    )

    pending_claims = PaymentClaim.objects.filter(
        status=PaymentClaimStatus.PENDING,
    ).filter(
        models_q_owner(owner)
    ).count()

    cfg = get_or_create_collection_settings(owner)
    payout = (
        payout_analytics(owner)
        if cfg.collection_mode == CollectionMode.PLATFORM_COLLECT and cfg.platform_collect_enabled
        else None
    )

    return {
        'collectionMode': cfg.collection_mode,
        'platformCollectEnabled': cfg.platform_collect_enabled,
        'showsPlatformPayouts': bool(payout),
        'markedReceived': float(totals['total'] or 0),
        # Backward-compatible aliases for older Account UI tiles
        'totalCollected': float(totals['total'] or 0),
        'totalCommission': float((payout or {}).get('totalCommission') or 0),
        'netEarnings': float(totals['total'] or 0) if not payout else float(payout.get('netEarnings') or 0),
        'pendingPayouts': float((payout or {}).get('pendingPayouts') or 0),
        'paidPayouts': float((payout or {}).get('paidPayouts') or 0),
        'commissionRate': float((payout or {}).get('commissionRate') or 0),
        'receiptCount': totals['count'] or 0,
        'messDepositsConfirmed': float(mess_received),
        'outstandingBills': float(outstanding),
        'pendingClaims': pending_claims,
        'collectionByMethod': [
            {
                'method': row['payment_method'],
                'amount': float(row['amount'] or 0),
                'count': row['count'],
            }
            for row in by_method
        ],
        'monthlyTrend': [
            {'month': month, 'amount': float(amount), 'gross': float(amount), 'net': float(amount)}
            for month, amount in sorted(monthly.items())
        ],
        'platformPayouts': payout,
        'instructions': serialize_instructions(cfg),
    }


def models_q_owner(owner):
    from django.db.models import Q

    return Q(bill__owner=owner) | Q(mess__owner=owner)


def collection_report(owner, *, year: int | None = None, month: int | None = None) -> dict:
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    txns = PaymentTransaction.objects.filter(
        bill__owner=owner,
        status=PaymentTransactionStatus.COMPLETED,
        completed_at__year=year,
        completed_at__month=month,
    ).select_related('bill')

    rows = [
        {
            'id': str(t.id),
            'source': 'bill',
            'billId': str(t.bill_id) if t.bill_id else '',
            'label': t.bill_name,
            'tenantName': t.tenant_name,
            'propertyName': t.property_name,
            'amount': float(t.amount),
            'paymentMethod': t.payment_method,
            'transactionId': t.transaction_id,
            'completedAt': t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in txns
    ]

    deposits = MemberDeposit.objects.filter(
        mess__owner=owner,
        is_deleted=False,
        status=DepositStatus.CONFIRMED,
        date__year=year,
        date__month=month,
    ).select_related('student', 'mess')

    for dep in deposits:
        rows.append(
            {
                'id': str(dep.id),
                'source': 'mess_deposit',
                'billId': '',
                'label': f'{dep.mess.name} deposit',
                'tenantName': dep.student.name if dep.student_id else '',
                'propertyName': dep.mess.name,
                'amount': float(dep.amount),
                'paymentMethod': dep.payment_method or PaymentMethod.CASH,
                'transactionId': dep.transaction_id or '',
                'completedAt': dep.date.isoformat(),
            }
        )

    total = sum(r['amount'] for r in rows)
    return {
        'year': year,
        'month': month,
        'total': total,
        'count': len(rows),
        'rows': rows,
        'generatedAt': timezone.now().isoformat(),
    }


def assert_owner(user) -> None:
    if user.role not in ('owner', 'admin'):
        raise ForbiddenError('Only owners can manage collection settings.')
