"""Owner subscription helpers and flat-limit enforcement."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TypedDict

from django.utils import timezone

from subscriptions.models import OwnerSubscription, PlanTier, SubscriptionPlan


class FlatLimitStatus(TypedDict):
    used: int
    max: int
    atLimit: bool
    nearLimit: bool
    planTier: str
    planName: str


DEFAULT_PLANS = [
    {
        'tier': PlanTier.FREE,
        'name': 'Free',
        'price': 0,
        'max_flats': 3,
        'features': ['Up to 3 flats', 'Basic billing'],
        'highlighted': False,
    },
    {
        'tier': PlanTier.BASIC,
        'name': 'Basic',
        'price': 500,
        'max_flats': 10,
        'features': ['Up to 10 flats', 'Bill templates', 'SMS reminders'],
        'highlighted': True,
    },
    {
        'tier': PlanTier.PREMIUM,
        'name': 'Premium',
        'price': 2000,
        'max_flats': -1,
        'features': ['Unlimited flats', 'Featured listings', 'Priority support'],
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
        return existing

    free_plan = SubscriptionPlan.objects.get(tier=PlanTier.FREE)
    cycle_start, cycle_end = _billing_cycle_dates()
    return OwnerSubscription.objects.create(
        owner=user,
        plan=free_plan,
        billing_cycle_start=cycle_start,
        billing_cycle_end=cycle_end,
    )


def get_flat_limit_status(user) -> FlatLimitStatus:
    sub = get_or_create_owner_subscription(user)
    plan = sub.plan
    max_flats = plan.max_flats
    used = sub.flats_used
    unlimited = max_flats < 0

    return {
        'used': used,
        'max': max_flats,
        'atLimit': not unlimited and used >= max_flats,
        'nearLimit': not unlimited and used >= max(1, int(max_flats * 0.8)),
        'planTier': plan.tier,
        'planName': plan.name,
    }


def assert_can_add_flat(user) -> None:
    from core.exceptions import InvalidError

    status = get_flat_limit_status(user)
    if status['atLimit']:
        raise InvalidError(
            f'Flat limit reached ({status["used"]}/{status["max"]}). '
            f'Upgrade your {status["planName"]} plan to add more flats.',
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
    return sub


def get_boost_option(boost_id: str) -> dict | None:
    return next((b for b in FEATURED_BOOST_OPTIONS if b['id'] == boost_id), None)
