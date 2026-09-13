"""Keep public listings in sync with mess seats and portfolio flats."""
from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from listings.models import Property, PropertyType


BILL_FIELDS = (
    'electricity_bill',
    'gas_bill',
    'internet_bill',
    'water_bill',
)


def copy_utility_bills(source, target) -> list[str]:
    changed = []
    for field in BILL_FIELDS:
        value = getattr(source, field, None)
        if getattr(target, field, None) != value:
            setattr(target, field, value)
            changed.append(field)
    return changed


def push_flat_bills_to_listing(flat) -> None:
    listing = flat.listing
    if listing is None:
        return
    if not any(getattr(flat, field) is not None for field in BILL_FIELDS):
        return
    changed = copy_utility_bills(flat, listing)
    if changed:
        listing.save(update_fields=changed + ['updated_at'])


def push_listing_bills_to_flat(listing) -> None:
    """Keep the flat form in step when this listing is one flat."""
    if listing.type != PropertyType.APARTMENT:
        return
    flats = list(listing.linked_flats.all()[:2])
    if len(flats) != 1:
        return
    changed = copy_utility_bills(listing, flats[0])
    if changed:
        flats[0].save(update_fields=changed + ['updated_at'])


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
    """Mirror mess inventory + marketing fields onto the linked public listing."""
    listing = mess.listing
    if listing is None:
        listing = _find_matching_listing(mess)
        if listing is not None:
            mess.listing = listing
            mess.save(update_fields=['listing', 'updated_at'])
    if listing is None:
        return None

    previous_open = listing.open_seats
    open_seats = int(mess.available_seats or 0)
    if int(mess.total_seats or 0) > 0:
        _apply_availability(listing, available=open_seats > 0, open_seats=open_seats)

    listing.name = mess.name or listing.name
    listing.address = mess.address or listing.address
    listing.city = mess.city or listing.city
    listing.area = mess.city or listing.area
    listing.rent = mess.monthly_fee
    listing.description = mess.description or listing.description
    listing.image_urls = list(mess.images or [])
    listing.facilities = list(mess.facilities or [])
    copy_utility_bills(mess, listing)
    listing.save(
        update_fields=[
            'name',
            'address',
            'city',
            'area',
            'rent',
            'description',
            'image_urls',
            'facilities',
            *BILL_FIELDS,
            'updated_at',
        ],
    )

    if int(mess.total_seats or 0) > 0:
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
    """A listing is available only while its linked flat is vacant."""
    listing = flat.listing
    if listing is None:
        return None
    refresh_listing_availability(listing)
    push_flat_bills_to_listing(flat)
    return listing


def linked_apartment_flat(listing):
    """The one flat this apartment listing is for, if any."""
    if getattr(listing, 'type', None) != PropertyType.APARTMENT:
        return None
    related = getattr(listing, 'linked_flats', None)
    if related is None:
        return None
    return related.select_related('building').order_by('created_at').first()


def apartment_is_bookable(listing) -> bool:
    from portfolio.models import FlatStatus

    flat = linked_apartment_flat(listing)
    if flat is None:
        return bool(listing.available)
    return flat.status == FlatStatus.AVAILABLE


def refresh_listing_availability(listing) -> None:
    from portfolio.models import FlatStatus

    if listing.type == PropertyType.APARTMENT and listing.linked_flats.exists():
        available = listing.linked_flats.filter(status=FlatStatus.AVAILABLE).exists()
    else:
        available = listing.available
    _apply_availability(listing, available=available, open_seats=None)


def bind_listing_to_flat(listing, flat) -> None:
    """One apartment listing belongs to one flat. Other links are cleared."""
    from portfolio.models import Flat

    Flat.objects.filter(listing=listing).exclude(pk=flat.pk).update(listing=None)
    previous_id = flat.listing_id if flat.listing_id and flat.listing_id != listing.id else None
    flat.listing = listing
    flat.save(update_fields=['listing', 'updated_at'])
    sync_flat_listing(flat)
    if previous_id:
        previous = Property.objects.filter(pk=previous_id).first()
        if previous is not None:
            refresh_listing_availability(previous)


def release_booking_occupancy(booking) -> None:
    """Free the flat when the booking that occupied it ends."""
    if not booking.flat_id:
        return
    from portfolio.models import Flat, FlatStatus, Tenancy, TenancyStatus

    flat = Flat.objects.select_related('building', 'listing').filter(pk=booking.flat_id).first()
    if flat is None:
        return
    tenancy = (
        Tenancy.objects.filter(
            flat=flat,
            status=TenancyStatus.ACTIVE,
            tenant_id=booking.renter_id,
        )
        .order_by('-start_date')
        .first()
    )
    if tenancy is None:
        return
    today = timezone.localdate()
    tenancy.status = TenancyStatus.ENDED
    tenancy.end_date = today
    tenancy.save(update_fields=['status', 'end_date', 'updated_at'])
    flat.status = FlatStatus.AVAILABLE
    flat.save(update_fields=['status', 'updated_at'])
    flat.building.refresh_counts()
    if flat.listing_id:
        refresh_listing_availability(flat.listing)


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
    generated_name = f'{building.name} Flat {flat.flat_number}'.strip()
    unit = (flat.flat_number or '').strip()
    address = (building.address or '').strip()
    if listing is None:
        match = Q(name__iexact=generated_name)
        if unit and address:
            match |= Q(unit_number__iexact=unit, address__iexact=address)
        if unit:
            match |= Q(name__iendswith=f'Flat {unit}')
        listing = (
            Property.objects.filter(
                owner_id=building.owner_id,
                type=PropertyType.APARTMENT,
            )
            .filter(match)
            .filter(Q(linked_flats__isnull=True) | Q(linked_flats=flat))
            .distinct()
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
        if unit and listing.unit_number != unit:
            listing.unit_number = unit
            updates.append('unit_number')
        if address and not (listing.address or '').strip():
            listing.address = address
            updates.append('address')
        if any(getattr(flat, field) is not None for field in BILL_FIELDS):
            updates.extend(copy_utility_bills(flat, listing))
        if publish and (
            not listing.published or listing.listing_status != ListingStatus.PUBLISHED
        ):
            listing.published = True
            listing.listing_status = ListingStatus.PUBLISHED
            updates.extend(['published', 'listing_status'])
        if updates:
            listing.save(update_fields=list(dict.fromkeys(updates + ['updated_at'])))
        if flat.listing_id != listing.id:
            bind_listing_to_flat(listing, flat)
        else:
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
        unit_number=unit,
        available=flat.status == FlatStatus.AVAILABLE,
        bedrooms=flat.bedrooms,
        bathrooms=flat.bathrooms,
        size_sqft=flat.area,
        floor_level=flat.floor_number,
        electricity_bill=flat.electricity_bill,
        gas_bill=flat.gas_bill,
        internet_bill=flat.internet_bill,
        water_bill=flat.water_bill,
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
    bind_listing_to_flat(listing, flat)
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
        electricity_bill=mess.electricity_bill,
        gas_bill=mess.gas_bill,
        internet_bill=mess.internet_bill,
        water_bill=mess.water_bill,
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
