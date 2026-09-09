"""Owner SMS credit wallet — system BulkSMSBD, plan free quota, purchasable packs."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.exceptions import InvalidError, NotFoundError
from mess.models import (
    OwnerSMSAccount,
    SMSCreditLedger,
    SMSCreditPackage,
    SMSCreditPurchase,
    SMSMessage,
)

DEFAULT_SMS_PACKAGES = [
    {
        'id': 'sms-50',
        'label': '50 SMS',
        'credits': 50,
        'price': 25,
        'description': 'Starter pack — ~৳0.50/SMS',
    },
    {
        'id': 'sms-200',
        'label': '200 SMS',
        'credits': 200,
        'price': 90,
        'description': 'Popular — save vs starter',
    },
    {
        'id': 'sms-500',
        'label': '500 SMS',
        'credits': 500,
        'price': 200,
        'description': 'Best value for active messes',
    },
]


def free_quota_for_tier(tier: str) -> int:
    tier = (tier or 'free').lower()
    if tier == 'premium':
        return int(getattr(settings, 'SMS_FREE_QUOTA_PREMIUM', 500))
    if tier == 'basic':
        return int(getattr(settings, 'SMS_FREE_QUOTA_BASIC', 100))
    return int(getattr(settings, 'SMS_FREE_QUOTA_FREE', 20))


def unit_price_bdt() -> Decimal:
    return Decimal(str(getattr(settings, 'SMS_CREDIT_UNIT_PRICE_BDT', 0.50)))


def current_period_key() -> str:
    return timezone.localdate().strftime('%Y-%m')


def list_active_packages() -> list[dict]:
    rows = list(
        SMSCreditPackage.objects.filter(is_active=True).order_by(
            'sort_order', 'credits', 'package_key'
        )
    )
    if not rows:
        return list(DEFAULT_SMS_PACKAGES)
    return [
        {
            'id': p.package_key,
            'label': p.label,
            'credits': p.credits,
            'price': float(p.price_bdt),
            'description': p.description,
        }
        for p in rows
    ]


def get_package_by_key(package_id: str) -> dict:
    pkg = SMSCreditPackage.objects.filter(
        package_key=package_id, is_active=True
    ).first()
    if pkg:
        return {
            'id': pkg.package_key,
            'label': pkg.label,
            'credits': pkg.credits,
            'price': float(pkg.price_bdt),
            'description': pkg.description,
        }
    fallback = next(
        (p for p in DEFAULT_SMS_PACKAGES if p['id'] == package_id), None
    )
    if not fallback:
        raise InvalidError('Unknown SMS package.')
    # Only allow hardcoded fallback when no DB packs exist at all
    if SMSCreditPackage.objects.exists():
        raise InvalidError('Unknown or inactive SMS package.')
    return fallback


def serialize_package(pkg: SMSCreditPackage) -> dict:
    return {
        'id': str(pkg.id),
        'packageKey': pkg.package_key,
        'label': pkg.label,
        'credits': pkg.credits,
        'priceBdt': float(pkg.price_bdt),
        'description': pkg.description,
        'isActive': pkg.is_active,
        'sortOrder': pkg.sort_order,
        'createdAt': pkg.created_at.isoformat(),
        'updatedAt': pkg.updated_at.isoformat(),
    }


def get_or_create_sms_account(owner) -> OwnerSMSAccount:
    account, _ = OwnerSMSAccount.objects.get_or_create(owner=owner)
    return account


@transaction.atomic
def ensure_monthly_free_quota(owner) -> OwnerSMSAccount:
    """Grant plan free SMS once per calendar month (subscription-based)."""
    from subscriptions.models import OwnerSubscription

    account = get_or_create_sms_account(owner)
    account = OwnerSMSAccount.objects.select_for_update().get(pk=account.pk)
    period = current_period_key()
    if account.free_quota_period == period:
        return account

    sub = (
        OwnerSubscription.objects.filter(owner=owner)
        .select_related('plan')
        .first()
    )
    tier = sub.plan.tier if sub else 'free'
    quota = free_quota_for_tier(tier)
    if quota > 0:
        account.balance += quota
        account.lifetime_granted += quota
        account.free_quota_period = period
        account.save(
            update_fields=[
                'balance',
                'lifetime_granted',
                'free_quota_period',
                'updated_at',
            ]
        )
        SMSCreditLedger.objects.create(
            account=account,
            entry_type=SMSCreditLedger.EntryType.FREE_QUOTA,
            credits=quota,
            balance_after=account.balance,
            note=f'Monthly free quota ({tier}) for {period}',
            metadata={'tier': tier, 'period': period},
        )
    else:
        account.free_quota_period = period
        account.save(update_fields=['free_quota_period', 'updated_at'])
    return account


def gateway_status() -> dict:
    provider = (getattr(settings, 'SMS_PROVIDER', 'console') or 'console').lower()
    configured = provider in ('bulksmsbd', 'bulksms', 'bulksmsbd.net') and bool(
        getattr(settings, 'SMS_API_KEY', '')
    )
    return {
        'provider': 'system',
        'channel': 'bulksmsbd' if configured else provider,
        'configured': configured or provider == 'console',
        'label': 'SmartBasa SMS (BulkSMSBD)'
        if configured
        else 'SmartBasa SMS (console / not live)',
    }


def serialize_wallet(owner) -> dict:
    account = ensure_monthly_free_quota(owner)
    from subscriptions.models import OwnerSubscription

    sub = (
        OwnerSubscription.objects.filter(owner=owner)
        .select_related('plan')
        .first()
    )
    tier = sub.plan.tier if sub else 'free'
    plan_name = sub.plan.name if sub else 'Free'
    return {
        'balance': account.balance,
        'lifetimeGranted': account.lifetime_granted,
        'lifetimePurchased': account.lifetime_purchased,
        'lifetimeUsed': account.lifetime_used,
        'period': account.free_quota_period or current_period_key(),
        'planTier': tier,
        'planName': plan_name,
        'monthlyFreeQuota': free_quota_for_tier(tier),
        'unitPriceBdt': float(unit_price_bdt()),
        'gateway': gateway_status(),
        'packages': list_active_packages(),
    }


def assert_can_send(owner, recipient_count: int) -> OwnerSMSAccount:
    if recipient_count <= 0:
        raise InvalidError('No recipients to send SMS.')
    account = ensure_monthly_free_quota(owner)
    account = OwnerSMSAccount.objects.select_for_update().get(pk=account.pk)
    if account.balance < recipient_count:
        raise InvalidError(
            f'Insufficient SMS credits ({account.balance} left, need {recipient_count}). '
            'Buy more SMS credits or wait for next month free quota.',
        )
    return account


@transaction.atomic
def debit_credits(
    owner,
    credits: int,
    *,
    mess=None,
    sms_message=None,
    note: str = '',
) -> OwnerSMSAccount:
    if credits <= 0:
        return ensure_monthly_free_quota(owner)
    account = OwnerSMSAccount.objects.select_for_update().get(
        pk=ensure_monthly_free_quota(owner).pk
    )
    if account.balance < credits:
        raise InvalidError('Insufficient SMS credits.')
    account.balance -= credits
    account.lifetime_used += credits
    account.save(update_fields=['balance', 'lifetime_used', 'updated_at'])
    SMSCreditLedger.objects.create(
        account=account,
        entry_type=SMSCreditLedger.EntryType.SEND_DEBIT,
        credits=-credits,
        balance_after=account.balance,
        note=note or f'Sent {credits} SMS',
        mess=mess,
        sms_message=sms_message,
        metadata={'credits': credits},
    )
    return account


@transaction.atomic
def purchase_sms_package(owner, package_id: str) -> dict:
    package = get_package_by_key(str(package_id))

    purchase = SMSCreditPurchase.objects.create(
        owner=owner,
        package_id=package['id'],
        credits=package['credits'],
        amount_bdt=package['price'],
        status=SMSCreditPurchase.Status.PENDING,
    )

    # Sandbox / platform catalog purchase — credit immediately (same pattern as boosts)
    account = OwnerSMSAccount.objects.select_for_update().get(
        pk=ensure_monthly_free_quota(owner).pk
    )
    account.balance += package['credits']
    account.lifetime_purchased += package['credits']
    account.save(update_fields=['balance', 'lifetime_purchased', 'updated_at'])
    entry = SMSCreditLedger.objects.create(
        account=account,
        entry_type=SMSCreditLedger.EntryType.PURCHASE,
        credits=package['credits'],
        balance_after=account.balance,
        note=f"Purchased {package['label']}",
        metadata={
            'packageId': package['id'],
            'amountBdt': float(package['price']),
            'purchaseId': str(purchase.id),
        },
    )
    purchase.status = SMSCreditPurchase.Status.PAID
    purchase.paid_at = timezone.now()
    purchase.ledger_entry = entry
    purchase.save(update_fields=['status', 'paid_at', 'ledger_entry', 'updated_at'])

    return {
        'purchaseId': str(purchase.id),
        'credits': package['credits'],
        'amountBdt': float(package['price']),
        'balance': account.balance,
        'package': package,
    }


@transaction.atomic
def admin_adjust_credits(
    owner,
    credits: int,
    *,
    note: str = '',
    admin_user=None,
) -> OwnerSMSAccount:
    """Positive credits grant; negative credits debit (admin adjustment)."""
    if credits == 0:
        raise InvalidError('credits must be non-zero.')
    account = OwnerSMSAccount.objects.select_for_update().get(
        pk=ensure_monthly_free_quota(owner).pk
    )
    new_balance = account.balance + credits
    if new_balance < 0:
        raise InvalidError(
            f'Adjustment would make balance negative ({account.balance} + {credits}).'
        )
    account.balance = new_balance
    if credits > 0:
        account.lifetime_granted += credits
        update_fields = ['balance', 'lifetime_granted', 'updated_at']
    else:
        account.lifetime_used += abs(credits)
        update_fields = ['balance', 'lifetime_used', 'updated_at']
    account.save(update_fields=update_fields)
    SMSCreditLedger.objects.create(
        account=account,
        entry_type=SMSCreditLedger.EntryType.ADJUSTMENT,
        credits=credits,
        balance_after=account.balance,
        note=note or ('Admin credit grant' if credits > 0 else 'Admin credit debit'),
        metadata={
            'adminId': str(admin_user.id) if admin_user else None,
            'adminPhone': getattr(admin_user, 'phone', None) if admin_user else None,
        },
    )
    return account


def serialize_ledger(owner, limit: int = 50) -> list[dict]:
    account = get_or_create_sms_account(owner)
    qs = (
        SMSCreditLedger.objects.filter(account=account)
        .select_related('mess', 'sms_message')
        .order_by('-created_at')[:limit]
    )
    return [
        {
            'id': str(e.id),
            'entryType': e.entry_type,
            'credits': e.credits,
            'balanceAfter': e.balance_after,
            'note': e.note,
            'messId': str(e.mess_id) if e.mess_id else None,
            'messName': e.mess.name if e.mess_id else None,
            'smsMessageId': str(e.sms_message_id) if e.sms_message_id else None,
            'createdAt': e.created_at.isoformat(),
            'metadata': e.metadata or {},
        }
        for e in qs
    ]


def serialize_owner_wallet_row(account: OwnerSMSAccount) -> dict:
    owner = account.owner
    from subscriptions.models import OwnerSubscription

    sub = (
        OwnerSubscription.objects.filter(owner=owner)
        .select_related('plan')
        .first()
    )
    tier = sub.plan.tier if sub else 'free'
    sent_qs = SMSMessage.objects.filter(sent_by=owner)
    sent_agg = sent_qs.aggregate(
        successful=Sum('successful'),
        failed=Sum('failed'),
        cost=Sum('cost'),
    )
    return {
        'ownerId': str(owner.id),
        'ownerName': owner.name or '',
        'ownerPhone': owner.phone,
        'balance': account.balance,
        'lifetimeGranted': account.lifetime_granted,
        'lifetimePurchased': account.lifetime_purchased,
        'lifetimeUsed': account.lifetime_used,
        'available': account.balance,
        'occupied': account.lifetime_used,
        'period': account.free_quota_period or current_period_key(),
        'planTier': tier,
        'planName': sub.plan.name if sub else 'Free',
        'monthlyFreeQuota': free_quota_for_tier(tier),
        'smsBatches': sent_qs.count(),
        'smsSuccessful': int(sent_agg['successful'] or 0),
        'smsFailed': int(sent_agg['failed'] or 0),
        'smsCostBdt': float(sent_agg['cost'] or 0),
        'updatedAt': account.updated_at.isoformat(),
    }


def platform_sms_overview() -> dict:
    wallet_agg = OwnerSMSAccount.objects.aggregate(
        balance=Sum('balance'),
        granted=Sum('lifetime_granted'),
        purchased=Sum('lifetime_purchased'),
        used=Sum('lifetime_used'),
    )
    msg_agg = SMSMessage.objects.aggregate(
        successful=Sum('successful'),
        failed=Sum('failed'),
        cost=Sum('cost'),
    )
    return {
        'ownerWallets': OwnerSMSAccount.objects.count(),
        'totalBalance': int(wallet_agg['balance'] or 0),
        'totalGranted': int(wallet_agg['granted'] or 0),
        'totalPurchased': int(wallet_agg['purchased'] or 0),
        'totalUsed': int(wallet_agg['used'] or 0),
        'smsBatches': SMSMessage.objects.count(),
        'smsSuccessful': int(msg_agg['successful'] or 0),
        'smsFailed': int(msg_agg['failed'] or 0),
        'smsCostBdt': float(msg_agg['cost'] or 0),
        'activePackages': SMSCreditPackage.objects.filter(is_active=True).count(),
        'gateway': gateway_status(),
        'unitPriceBdt': float(unit_price_bdt()),
        'freeQuota': {
            'free': free_quota_for_tier('free'),
            'basic': free_quota_for_tier('basic'),
            'premium': free_quota_for_tier('premium'),
        },
    }
