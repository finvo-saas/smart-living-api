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


def attach_listing_to_flat(flat, property_id) -> None:
    """Owner linked a public listing when creating/updating a flat."""
    if not property_id:
        if flat.listing_id:
            flat.listing = None
            flat.save(update_fields=['listing', 'updated_at'])
        return
    listing = Property.objects.filter(pk=property_id, owner_id=flat.building.owner_id).first()
    if listing is None:
        return
    if listing.type != PropertyType.APARTMENT:
        return
    flat.listing = listing
    flat.save(update_fields=['listing', 'updated_at'])
    sync_flat_listing(flat)


def ensure_listing_for_flat(flat, *, publish: bool = True) -> Property:
    """Create or publish a public apartment listing for a portfolio flat."""
    from listings.models import ListingStatus

    building = flat.building
    listing = flat.listing
    if listing is None:
        listing = (
            Property.objects.filter(
                owner_id=building.owner_id,
                type=PropertyType.APARTMENT,
                name__iexact=f'{building.name} Flat {flat.flat_number}'.strip(),
            )
            .order_by('-published', '-created_at')
            .first()
        )

    if listing is not None:
        updates = []
        if flat.bedrooms is not None and listing.bedrooms != flat.bedrooms:
            listing.bedrooms = flat.bedrooms
            updates.append('bedrooms')
        if flat.bathrooms is not None and listing.bathrooms != flat.bathrooms:
            listing.bathrooms = flat.bathrooms
            updates.append('bathrooms')
        if flat.area is not None and listing.size_sqft != flat.area:
            listing.size_sqft = flat.area
            updates.append('size_sqft')
        if flat.floor_number is not None and listing.floor_level != flat.floor_number:
            listing.floor_level = flat.floor_number
            updates.append('floor_level')
        if listing.rent != flat.rent:
            listing.rent = flat.rent
            updates.append('rent')
        if publish and (
            not listing.published or listing.listing_status != ListingStatus.PUBLISHED
        ):
            listing.published = True
            listing.listing_status = ListingStatus.PUBLISHED
            updates.extend(['published', 'listing_status'])
        if updates:
            listing.save(update_fields=list(dict.fromkeys(updates + ['updated_at'])))
        if flat.listing_id != listing.id:
            flat.listing = listing
            flat.save(update_fields=['listing', 'updated_at'])
        sync_flat_listing(flat)
        return listing

    from portfolio.models import FlatStatus

    listing = Property.objects.create(
        owner=building.owner,
        name=f'{building.name} Flat {flat.flat_number}',
        type=PropertyType.APARTMENT,
        rent=flat.rent,
        area=building.city,
        address=building.address,
        city=building.city,
        available=flat.status == FlatStatus.AVAILABLE,
        bedrooms=flat.bedrooms,
        bathrooms=flat.bathrooms,
        size_sqft=flat.area,
        floor_level=flat.floor_number,
        tenant_type='any',
        deposit_months=2,
        description=(
            f'{building.name} Flat {flat.flat_number} — '
            f'{flat.bedrooms or "?"} bed, {flat.bathrooms or "?"} bath'
            f'{f", {flat.area} sqft" if flat.area else ""}. '
            f'Managed unit with live occupancy.'
        ),
        published=publish,
        listing_status=ListingStatus.PUBLISHED if publish else ListingStatus.DRAFT,
        last_confirmed_at=timezone.now(),
    )
    flat.listing = listing
    flat.save(update_fields=['listing', 'updated_at'])
    sync_flat_listing(flat)
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
