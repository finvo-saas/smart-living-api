"""Keep public listings in sync with mess seats and portfolio flats."""
from __future__ import annotations

from django.utils import timezone

from listings.models import Property, PropertyType


def _apply_availability(listing: Property, available: bool, open_seats=None):
    now = timezone.now()
    listing.available = available
    listing.last_confirmed_at = now
    if open_seats is not None:
        listing.open_seats = open_seats
    if available:
        listing.flagged_unavailable_at = None
    else:
        listing.flagged_unavailable_at = now
    fields = [
        'available',
        'last_confirmed_at',
        'flagged_unavailable_at',
        'updated_at',
    ]
    if open_seats is not None:
        fields.append('open_seats')
    listing.save(update_fields=fields)


def sync_mess_listing(mess) -> Property | None:
    """Mirror mess available_seats onto the linked public listing."""
    listing = mess.listing
    if listing is None:
        listing = _find_matching_listing(mess)
        if listing is not None:
            mess.listing = listing
            mess.save(update_fields=['listing', 'updated_at'])
    if listing is None:
        return None
    if int(mess.total_seats or 0) == 0:
        return listing

    previous_open = listing.open_seats
    open_seats = int(mess.available_seats or 0)
    _apply_availability(listing, available=open_seats > 0, open_seats=open_seats)
    from listings.services.vacancy_flash import maybe_flash_on_seat_increase

    maybe_flash_on_seat_increase(listing, previous_open, open_seats)
    return listing


def link_listing_to_mess(prop: Property) -> None:
    """When a mess/hostel listing is created, attach matching mess ops if any."""
    if prop.type not in (PropertyType.MESS, PropertyType.HOSTEL):
        return
    from mess.models import Mess

    mess = (
        Mess.objects.filter(
            owner_id=prop.owner_id,
            is_deleted=False,
            name__iexact=prop.name.strip(),
        )
        .first()
    )
    if mess is None:
        return
    if mess.listing_id != prop.id:
        mess.listing = prop
        mess.save(update_fields=['listing', 'updated_at'])
    sync_mess_listing(mess)


def attach_listing_to_mess(mess, property_id) -> None:
    """Owner linked a public listing when creating/updating a mess."""
    if not property_id:
        sync_mess_listing(mess)
        return
    listing = Property.objects.filter(pk=property_id, owner_id=mess.owner_id).first()
    if listing is None:
        return
    mess.listing = listing
    mess.save(update_fields=['listing', 'updated_at'])
    sync_mess_listing(mess)


def sync_flat_listing(flat) -> Property | None:
    """A listing stays available if any linked flat is still vacant."""
    listing = flat.listing
    if listing is None:
        return None
    from portfolio.models import FlatStatus

    any_open = listing.linked_flats.filter(status=FlatStatus.AVAILABLE).exists()
    _apply_availability(listing, available=any_open, open_seats=None)
    return listing


def _find_matching_listing(mess) -> Property | None:
    return (
        Property.objects.filter(
            owner_id=mess.owner_id,
            type__in=(PropertyType.MESS, PropertyType.HOSTEL),
            name__iexact=mess.name.strip(),
        )
        .order_by('-published', '-created_at')
        .first()
    )


def ensure_listing_for_mess(mess) -> Property:
    """Guarantee a public Property exists so seekers can book from mess pages."""
    from listings.models import Gender, ListingStatus, MealPlan

    listing = sync_mess_listing(mess)
    if listing is not None:
        if not listing.published or listing.listing_status != ListingStatus.PUBLISHED:
            listing.published = True
            listing.listing_status = ListingStatus.PUBLISHED
            listing.save(update_fields=['published', 'listing_status', 'updated_at'])
        return listing

    meals = int(getattr(mess, 'meals_per_day', 3) or 3)
    meal_plan = {
        1: MealPlan.BREAKFAST,
        2: MealPlan.LUNCH,
        3: MealPlan.ALL,
        4: MealPlan.ALL,
    }.get(meals, MealPlan.ALL)
    gender = mess.gender if mess.gender in dict(Gender.choices) else None

    listing = Property.objects.create(
        owner=mess.owner,
        name=mess.name,
        type=PropertyType.MESS,
        rent=mess.monthly_fee,
        area=mess.city,
        address=mess.address,
        city=mess.city,
        available=int(mess.available_seats or 0) > 0,
        gender=gender,
        meal_included=True,
        meal_plan=meal_plan,
        meal_cost=mess.meal_monthly_charge,
        image_urls=list(mess.images or []),
        facilities=list(mess.facilities or []),
        description=mess.description
        or f'{mess.name} — managed mess with live seat inventory.',
        published=True,
        listing_status=ListingStatus.PUBLISHED,
        open_seats=int(mess.available_seats or 0),
        last_confirmed_at=timezone.now(),
    )
    mess.listing = listing
    mess.save(update_fields=['listing', 'updated_at'])
    sync_mess_listing(mess)
    return listing
