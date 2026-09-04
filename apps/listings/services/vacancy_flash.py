"""Vacancy Flash — short featured burst when inventory frees up."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from listings.models import Property


def trigger_vacancy_flash(listing: Property, hours: int = 48) -> dict | None:
    """When seats/rooms become available, boost listing for a short window."""
    if not listing or not listing.published:
        return None
    now = timezone.now()
    until = now + timedelta(hours=hours)

    # Extend if already featured briefly; otherwise set featured
    if listing.featured and listing.featured_until and listing.featured_until > until:
        featured_until = listing.featured_until
    else:
        listing.featured = True
        listing.featured_until = until
        listing.save(update_fields=['featured', 'featured_until', 'updated_at'])
        featured_until = until

    from subscriptions.models import AdCampaign

    campaign = AdCampaign.objects.create(
        owner_id=listing.owner_id,
        name=f'Vacancy Flash · {listing.name}'[:120],
        target_type=AdCampaign.TargetType.LISTING,
        listing=listing,
        status=AdCampaign.Status.ACTIVE,
        starts_at=now,
        ends_at=until,
        daily_budget=0,
        bid_amount=80,
        quality_score=min(95, 60 + int(listing.rating or 0) * 5),
        vacancy_flash=True,
    )
    return {
        'campaignId': str(campaign.id),
        'featuredUntil': featured_until.isoformat(),
        'hours': hours,
    }


def maybe_flash_on_seat_increase(listing: Property, previous_open: int | None, new_open: int):
    prev = previous_open if previous_open is not None else 0
    if prev <= 0 and new_open > 0:
        return trigger_vacancy_flash(listing)
    return None
