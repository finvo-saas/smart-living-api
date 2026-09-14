"""People an owner or renter is allowed to message."""
from __future__ import annotations


def _person(user, *, context: str, context_id: str = '', label: str = '') -> dict | None:
    if user is None or not getattr(user, 'is_active', True):
        return None
    name = user.name or f'User {str(user.phone or "")[-4:]}'
    avatar = ''
    photo = getattr(user, 'profile_photo', None)
    if photo:
        try:
            avatar = photo.url
        except Exception:  # noqa: BLE001
            avatar = ''
    return {
        'userId': str(user.id),
        'name': name,
        'avatar': avatar,
        'context': context,
        'contextId': context_id or '',
        'label': label or context,
    }


def chat_contacts(user) -> list[dict]:
    """Owners see their renters. Renters see their owners. One row per person."""
    from bookings.models import PropertyBooking
    from hotels.models import Hotel, HotelBooking
    from mess.models import Mess, MessStudent
    from portfolio.models import Tenancy, TenancyStatus

    found: dict[str, dict] = {}

    def add(person: dict | None) -> None:
        if person is None or person['userId'] == str(user.id):
            return
        found.setdefault(person['userId'], person)

    tenancies = (
        Tenancy.objects.filter(status=TenancyStatus.ACTIVE)
        .select_related('tenant', 'flat__building__owner', 'flat__listing')
        .filter(flat__building__owner=user)[:80]
    )
    for tenancy in tenancies:
        flat = tenancy.flat
        listing = getattr(flat, 'listing', None)
        label = f'{flat.building.name} · Flat {flat.flat_number}'
        add(_person(tenancy.tenant, context='tenancy', context_id=str(flat.id), label=label))
        if listing is not None and not found.get(str(tenancy.tenant_id), {}).get('propertyId'):
            row = found.get(str(tenancy.tenant_id))
            if row is not None:
                row['propertyId'] = str(listing.id)
                row['propertyName'] = listing.name

    mine = (
        Tenancy.objects.filter(status=TenancyStatus.ACTIVE, tenant=user)
        .select_related('flat__building__owner', 'flat__listing')[:40]
    )
    for tenancy in mine:
        owner = tenancy.flat.building.owner
        listing = getattr(tenancy.flat, 'listing', None)
        person = _person(
            owner,
            context='tenancy',
            context_id=str(tenancy.flat_id),
            label=f'{tenancy.flat.building.name} · Flat {tenancy.flat.flat_number}',
        )
        if person and listing is not None:
            person['propertyId'] = str(listing.id)
            person['propertyName'] = listing.name
        add(person)

    bookings = (
        PropertyBooking.objects.filter(is_deleted=False)
        .filter(owner=user)
        .select_related('renter', 'property')
        .order_by('-updated_at')[:80]
    )
    for booking in bookings:
        person = _person(
            booking.renter,
            context='booking',
            context_id=str(booking.id),
            label=booking.property.name if booking.property_id else 'Booking',
        )
        if person and booking.property_id:
            person['propertyId'] = str(booking.property_id)
            person['propertyName'] = booking.property.name
        add(person)

    as_renter = (
        PropertyBooking.objects.filter(is_deleted=False, renter=user)
        .select_related('owner', 'property')
        .order_by('-updated_at')[:40]
    )
    for booking in as_renter:
        person = _person(
            booking.owner,
            context='booking',
            context_id=str(booking.id),
            label=booking.property.name if booking.property_id else 'Booking',
        )
        if person and booking.property_id:
            person['propertyId'] = str(booking.property_id)
            person['propertyName'] = booking.property.name
        add(person)

    hotels = Hotel.objects.filter(owner=user, is_deleted=False).values_list('id', flat=True)
    guest_bookings = (
        HotelBooking.objects.filter(hotel_id__in=hotels)
        .exclude(status='cancelled')
        .select_related('user', 'hotel')
        .order_by('-updated_at')[:40]
    )
    for booking in guest_bookings:
        add(_person(booking.user, context='hotel', context_id=str(booking.hotel_id), label=booking.hotel.name))

    my_stays = (
        HotelBooking.objects.filter(user=user)
        .exclude(status='cancelled')
        .select_related('hotel__owner')
        .order_by('-updated_at')[:20]
    )
    for booking in my_stays:
        add(_person(booking.hotel.owner, context='hotel', context_id=str(booking.hotel_id), label=booking.hotel.name))

    owned_messes = Mess.objects.filter(owner=user, is_deleted=False).values_list('id', flat=True)
    students = (
        MessStudent.objects.filter(
            mess_id__in=owned_messes,
            is_active=True,
            is_deleted=False,
            user__isnull=False,
        )
        .select_related('user', 'mess')[:80]
    )
    for student in students:
        add(_person(student.user, context='mess', context_id=str(student.mess_id), label=student.mess.name))

    enrolled = (
        MessStudent.objects.filter(user=user, is_active=True, is_deleted=False)
        .select_related('mess__owner')[:20]
    )
    for student in enrolled:
        add(_person(student.mess.owner, context='mess', context_id=str(student.mess_id), label=student.mess.name))

    return list(found.values())


def can_message(user, other, *, property_id=None) -> bool:
    if other is None or other.id == user.id or not other.is_active:
        return False
    roles = {getattr(user, 'role', ''), getattr(other, 'role', '')}
    if roles == {'owner', 'renter'} or 'admin' in roles:
        return True
    if property_id:
        from listings.models import Property

        prop = Property.objects.filter(pk=property_id).first()
        if prop is not None and other.id == prop.owner_id and (
            prop.published or user.id == prop.owner_id
        ):
            return True
    return any(row['userId'] == str(other.id) for row in chat_contacts(user))
