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
    max_messes = models.IntegerField(default=1)  # -1 = unlimited
    max_hotels = models.IntegerField(default=1)  # -1 = unlimited
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

    @property
    def messes_used(self) -> int:
        from mess.models import Mess

        return Mess.objects.filter(owner=self.owner, is_deleted=False).count()

    @property
    def hotels_used(self) -> int:
        from hotels.models import Hotel

        return Hotel.objects.filter(owner=self.owner, is_deleted=False).count()


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
        null=True,
        blank=True,
    )
    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='boosts',
        null=True,
        blank=True,
    )
    mess = models.ForeignKey(
        'mess.Mess',
        on_delete=models.CASCADE,
        related_name='boosts',
        null=True,
        blank=True,
    )
    target_type = models.CharField(max_length=20, default='listing', db_index=True)
    boost_option_id = models.CharField(max_length=64)
    duration_days = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_at = models.DateTimeField(default=timezone.now)
    featured_until = models.DateField()

    class Meta:
        db_table = 'subscriptions_featured_boost'
        ordering = ('-paid_at',)


class AdCampaign(UUIDModel, TimestampedModel):
    """Time-boxed ad campaign with inventory awareness and basic analytics."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        ENDED = 'ended', 'Ended'

    class TargetType(models.TextChoices):
        LISTING = 'listing', 'Listing'
        MESS = 'mess', 'Mess'
        HOTEL = 'hotel', 'Hotel'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ad_campaigns',
    )
    name = models.CharField(max_length=120)
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    listing = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='ad_campaigns',
        null=True,
        blank=True,
    )
    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.CASCADE,
        related_name='ad_campaigns',
        null=True,
        blank=True,
    )
    mess = models.ForeignKey(
        'mess.Mess',
        on_delete=models.CASCADE,
        related_name='ad_campaigns',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    daily_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=50)
    quality_score = models.PositiveSmallIntegerField(default=50)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vacancy_flash = models.BooleanField(
        default=False,
        help_text='Auto-created 24–72h burst when inventory frees up.',
    )

    class Meta:
        db_table = 'subscriptions_ad_campaign'
        ordering = ('-created_at',)

    @property
    def is_live(self) -> bool:
        now = timezone.now()
        return (
            self.status == self.Status.ACTIVE
            and self.starts_at <= now <= self.ends_at
        )

    @property
    def rank_score(self) -> float:
        """Auction + quality ranking score."""
        return float(self.bid_amount) * (self.quality_score / 100.0)

