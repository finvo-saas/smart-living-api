from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimestampedModel, UUIDModel
from listings.models import Property


class PlanTier(models.TextChoices):
    FREE = 'free', 'Free'
    BASIC = 'basic', 'Basic'
    PREMIUM = 'premium', 'Premium'


class SubscriptionPlan(UUIDModel, TimestampedModel):
    tier = models.CharField(max_length=20, choices=PlanTier.choices, unique=True)
    name = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_flats = models.IntegerField(default=3)  # -1 = unlimited
    features = models.JSONField(default=list)
    highlighted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'subscriptions_plan'
        ordering = ('price',)

    def __str__(self):
        return self.name


class OwnerSubscription(UUIDModel, TimestampedModel):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription',
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    billing_cycle_start = models.DateField()
    billing_cycle_end = models.DateField()
    active_featured_listings = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'subscriptions_owner_subscription'

    def __str__(self):
        return f'{self.owner.phone}:{self.plan.tier}'

    @property
    def flats_used(self) -> int:
        from portfolio.models import Flat

        return Flat.objects.filter(building__owner=self.owner).count()


class FeaturedBoost(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='featured_boosts',
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='boosts',
    )
    boost_option_id = models.CharField(max_length=64)
    duration_days = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_at = models.DateTimeField(default=timezone.now)
    featured_until = models.DateField()

    class Meta:
        db_table = 'subscriptions_featured_boost'
        ordering = ('-paid_at',)
