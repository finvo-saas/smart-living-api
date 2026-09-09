"""Owner subscription helpers and per-module limit enforcement."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TypedDict

from django.utils import timezone

from subscriptions.models import OwnerSubscription, PlanTier, SubscriptionPlan


class ModuleLimitStatus(TypedDict):
    used: int
    max: int
    atLimit: bool
    nearLimit: bool


class FlatLimitStatus(TypedDict):
    used: int
    max: int
    atLimit: bool
    nearLimit: bool
    planTier: str
    planName: str


class OwnerUsageStatus(TypedDict):
    planTier: str
    planName: str
    enabledVerticals: list[str]
    primaryFocus: str
    mess: ModuleLimitStatus
    apartment: ModuleLimitStatus
    hotel: ModuleLimitStatus
    # Legacy flat-shaped fields kept for older clients
    used: int
    max: int
    atLimit: bool
    nearLimit: bool


DEFAULT_PLANS = [
    {
        'tier': PlanTier.FREE,
        'name': 'Free',
        'price': 0,
        'max_flats': 3,
        'max_messes': 1,
        'max_hotels': 1,
        'features': [
            '1 mess · 3 flats · 1 hotel',
            'Basic billing',
            '20 free SMS / month',
        ],
        'highlighted': False,
    },
    {
        'tier': PlanTier.BASIC,
        'name': 'Basic',
        'price': 500,
        'max_flats': 10,
        'max_messes': 3,
        'max_hotels': 3,
        'features': [
            '3 messes · 10 flats · 3 hotels',
            'Bill templates',
            '100 free SMS / month',
            'Buy extra SMS credits',
        ],
        'highlighted': True,
    },
    {
        'tier': PlanTier.PREMIUM,
        'name': 'Premium',
        'price': 2000,
        'max_flats': -1,
        'max_messes': -1,
        'max_hotels': -1,
        'features': [
            'Unlimited messes, flats & hotels',
            'Featured listings',
            '500 free SMS / month',
            'Priority support',
        ],
        'highlighted': False,
    },
]

FEATURED_BOOST_OPTIONS = [
    {
        'id': 'boost-7',
        'label': '7-day boost',
        'durationDays': 7,
        'price': 299,
        'description': 'Featured badge + priority in search for one week',
    },
    {
        'id': 'boost-30',
        'label': '30-day boost',
        'durationDays': 30,
        'price': 899,
        'description': 'Best value — stay on top of discovery for a month',
    },
]


def ensure_default_plans() -> None:
    for spec in DEFAULT_PLANS:
        SubscriptionPlan.objects.update_or_create(
            tier=spec['tier'],
            defaults={
                'name': spec['name'],
                'price': spec['price'],
                'max_flats': spec['max_flats'],
                'max_messes': spec['max_messes'],
                'max_hotels': spec['max_hotels'],
                'features': spec['features'],
                'highlighted': spec['highlighted'],
                'is_active': True,
            },
        )


def _billing_cycle_dates() -> tuple[date, date]:
    today = timezone.localdate()
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end


def get_or_create_owner_subscription(user) -> OwnerSubscription:
    ensure_default_plans()
    existing = OwnerSubscription.objects.filter(owner=user).select_related('plan').first()
    if existing:
        # Keep SMS monthly free quota in sync when owner is active
        from mess.services.sms_credits import ensure_monthly_free_quota

        ensure_monthly_free_quota(user)
        return existing

    free_plan = SubscriptionPlan.objects.get(tier=PlanTier.FREE)
    cycle_start, cycle_end = _billing_cycle_dates()
    sub = OwnerSubscription.objects.create(
        owner=user,
        plan=free_plan,
        billing_cycle_start=cycle_start,
        billing_cycle_end=cycle_end,
    )
    from mess.services.sms_credits import ensure_monthly_free_quota

    ensure_monthly_free_quota(user)
    return sub


def _module_status(used: int, max_value: int) -> ModuleLimitStatus:
    unlimited = max_value < 0
    return {
        'used': used,
        'max': max_value,
        'atLimit': not unlimited and used >= max_value,
        'nearLimit': not unlimited and used >= max(1, int(max_value * 0.8)),
    }


def get_owner_usage_status(user) -> OwnerUsageStatus:
    """Per-module usage for mess / flats / hotels, plus legacy flat fields."""
    sub = get_or_create_owner_subscription(user)
    plan = sub.plan
    mess = _module_status(sub.messes_used, plan.max_messes)
    apartment = _module_status(sub.flats_used, plan.max_flats)
    hotel = _module_status(sub.hotels_used, plan.max_hotels)

    enabled = []
    if hasattr(user, 'owner_verticals_list'):
        enabled = list(user.owner_verticals_list())
    elif getattr(user, 'owner_enabled_verticals', None):
        enabled = list(user.owner_enabled_verticals or [])

    primary = getattr(user, 'owner_primary_focus', '') or ''

    return {
        'planTier': plan.tier,
        'planName': plan.name,
        'enabledVerticals': enabled,
        'primaryFocus': primary,
        'mess': mess,
        'apartment': apartment,
        'hotel': hotel,
        # Backward-compatible flat shape (apartment module)
        'used': apartment['used'],
        'max': apartment['max'],
        'atLimit': apartment['atLimit'],
        'nearLimit': apartment['nearLimit'],
    }


def get_flat_limit_status(user) -> FlatLimitStatus:
    """Legacy apartment-only shape — prefer get_owner_usage_status."""
    usage = get_owner_usage_status(user)
    return {
        'used': usage['apartment']['used'],
        'max': usage['apartment']['max'],
        'atLimit': usage['apartment']['atLimit'],
        'nearLimit': usage['apartment']['nearLimit'],
        'planTier': usage['planTier'],
        'planName': usage['planName'],
    }


def assert_can_add_flat(user) -> None:
    from core.exceptions import InvalidError

    status = get_flat_limit_status(user)
    if status['atLimit']:
        raise InvalidError(
            f'Flat limit reached ({status["used"]}/{status["max"]}). '
            f'Upgrade your {status["planName"]} plan to add more flats.',
        )


def assert_can_add_mess(user) -> None:
    from core.exceptions import InvalidError

    status = get_owner_usage_status(user)['mess']
    if status['atLimit']:
        plan_name = get_or_create_owner_subscription(user).plan.name
        raise InvalidError(
            f'Mess limit reached ({status["used"]}/{status["max"]}). '
            f'Upgrade your {plan_name} plan to add more messes.',
        )


def assert_can_add_hotel(user) -> None:
    from core.exceptions import InvalidError

    status = get_owner_usage_status(user)['hotel']
    if status['atLimit']:
        plan_name = get_or_create_owner_subscription(user).plan.name
        raise InvalidError(
            f'Hotel limit reached ({status["used"]}/{status["max"]}). '
            f'Upgrade your {plan_name} plan to add more hotels.',
        )


def upgrade_owner_plan(user, tier: str) -> OwnerSubscription:
    from core.exceptions import InvalidError

    ensure_default_plans()
    if tier not in (PlanTier.BASIC, PlanTier.PREMIUM):
        raise InvalidError('Upgrade tier must be basic or premium.')

    plan = SubscriptionPlan.objects.get(tier=tier)
    sub = get_or_create_owner_subscription(user)
    sub.plan = plan
    cycle_start, cycle_end = _billing_cycle_dates()
    sub.billing_cycle_start = cycle_start
    sub.billing_cycle_end = cycle_end
    sub.save(update_fields=['plan', 'billing_cycle_start', 'billing_cycle_end', 'updated_at'])
    # Reset period key so upgraded plan free quota can grant immediately
    from mess.models import OwnerSMSAccount
    from mess.services.sms_credits import ensure_monthly_free_quota

    account = OwnerSMSAccount.objects.filter(owner=user).first()
    if account:
        account.free_quota_period = ''
        account.save(update_fields=['free_quota_period', 'updated_at'])
    ensure_monthly_free_quota(user)
    return sub


def get_boost_option(boost_id: str) -> dict | None:
    return next((b for b in FEATURED_BOOST_OPTIONS if b['id'] == boost_id), None)
