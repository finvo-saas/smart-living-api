"""Ad campaign create/activate with inventory checks."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from subscriptions.models import AdCampaign


SLOT_CAP_PER_OWNER = 5


def create_campaign(owner, data: dict) -> AdCampaign:
    target_type = data.get('targetType') or AdCampaign.TargetType.LISTING
    starts = data.get('startsAt') or timezone.now()
    ends = data.get('endsAt') or (starts + timedelta(days=int(data.get('durationDays') or 7)))
    if ends <= starts:
        raise InvalidError('endsAt must be after startsAt.')

    active_count = AdCampaign.objects.filter(
        owner=owner,
        status=AdCampaign.Status.ACTIVE,
        ends_at__gte=timezone.now(),
    ).count()
    if active_count >= SLOT_CAP_PER_OWNER:
        raise InvalidError(f'Active campaign slot cap is {SLOT_CAP_PER_OWNER}.')

    prop = hotel = mess = None
    quality = 50
    if target_type == AdCampaign.TargetType.LISTING:
        from listings.models import Property

        try:
            prop = Property.objects.get(pk=data['listingId'])
        except (Property.DoesNotExist, KeyError) as exc:
            raise NotFoundError('Listing not found.') from exc
        if prop.owner_id != owner.id and owner.role != 'admin':
            raise ForbiddenError('You can only advertise your own listings.')
        if not prop.published or not prop.available:
            raise InvalidError('Only published available listings can be advertised.')
        # Mess inventory awareness
        if prop.type in ('mess', 'hostel') and prop.open_seats == 0:
            raise InvalidError('Cannot advertise a full mess/hostel with zero open seats.')
        quality = min(95, 40 + int((prop.rating or 0) * 8) + (15 if prop.verified else 0))
    elif target_type == AdCampaign.TargetType.MESS:
        from mess.models import Mess

        try:
            mess = Mess.objects.get(pk=data['messId'])
        except (Mess.DoesNotExist, KeyError) as exc:
            raise NotFoundError('Mess not found.') from exc
        if mess.owner_id != owner.id and owner.role != 'admin':
            raise ForbiddenError('You can only advertise your own mess.')
        if mess.available_seats <= 0:
            raise InvalidError('Cannot advertise a mess with no available seats.')
        quality = 55
    elif target_type == AdCampaign.TargetType.HOTEL:
        from hotels.models import Hotel

        try:
            hotel = Hotel.objects.get(pk=data['hotelId'])
        except (Hotel.DoesNotExist, KeyError) as exc:
            raise NotFoundError('Hotel not found.') from exc
        if hotel.owner_id != owner.id and owner.role != 'admin':
            raise ForbiddenError('You can only advertise your own hotels.')
        quality = 50
    else:
        raise InvalidError('Invalid targetType.')

    status = data.get('status') or AdCampaign.Status.ACTIVE
    campaign = AdCampaign.objects.create(
        owner=owner,
        name=(data.get('name') or 'Campaign')[:120],
        target_type=target_type,
        listing=prop,
        hotel=hotel,
        mess=mess,
        status=status,
        starts_at=starts,
        ends_at=ends,
        daily_budget=data.get('dailyBudget') or 0,
        bid_amount=data.get('bidAmount') or 50,
        quality_score=int(data.get('qualityScore') or quality),
        vacancy_flash=bool(data.get('vacancyFlash')),
    )
    if campaign.is_live and prop:
        prop.featured = True
        prop.featured_until = ends
        prop.save(update_fields=['featured', 'featured_until', 'updated_at'])
    return campaign


def serialize_campaign(c: AdCampaign) -> dict:
    return {
        'id': str(c.id),
        'name': c.name,
        'targetType': c.target_type,
        'listingId': str(c.listing_id) if c.listing_id else None,
        'messId': str(c.mess_id) if c.mess_id else None,
        'hotelId': str(c.hotel_id) if c.hotel_id else None,
        'status': c.status,
        'startsAt': c.starts_at.isoformat(),
        'endsAt': c.ends_at.isoformat(),
        'dailyBudget': float(c.daily_budget),
        'bidAmount': float(c.bid_amount),
        'qualityScore': c.quality_score,
        'rankScore': round(c.rank_score, 2),
        'impressions': c.impressions,
        'clicks': c.clicks,
        'spend': float(c.spend),
        'vacancyFlash': c.vacancy_flash,
        'isLive': c.is_live,
        'createdAt': c.created_at.isoformat(),
    }


def campaign_analytics(owner) -> dict:
    qs = AdCampaign.objects.filter(owner=owner)
    active = qs.filter(status=AdCampaign.Status.ACTIVE, ends_at__gte=timezone.now())
    return {
        'totalCampaigns': qs.count(),
        'activeCampaigns': active.count(),
        'impressions': sum(c.impressions for c in qs),
        'clicks': sum(c.clicks for c in qs),
        'spend': round(sum(float(c.spend) for c in qs), 2),
        'vacancyFlashes': qs.filter(vacancy_flash=True).count(),
        'slotCap': SLOT_CAP_PER_OWNER,
        'slotsUsed': active.count(),
        'topCampaigns': [
            serialize_campaign(c)
            for c in qs.order_by('-impressions', '-created_at')[:5]
        ],
    }
