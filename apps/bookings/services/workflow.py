from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from bookings.models import BookingMode, BookingStatus, PropertyBooking
from core.exceptions import (
    ConflictError,
    ForbiddenError,
    InvalidError,
    InvalidStateError,
    NotFoundError,
    ReasonRequiredError,
    UnavailableError,
    UnpublishedError,
)
from listings.models import ListingStatus, Property, PropertyType


ACTIVE_STATUSES = (BookingStatus.PENDING, BookingStatus.APPROVED)


def _property_image(prop: Property) -> str:
    urls = list(prop.image_urls or [])
    if urls:
        return urls[0]
    first = prop.image_files.first()
    if first:
        return first.resolved_url()
    return ''


def _display_name(user) -> str:
    return user.name or f'User {user.phone[-4:]}'


@transaction.atomic
def create_booking(user, data: dict) -> PropertyBooking:
    """CIMS is optional. Renters book a listing, which occupies its linked flat."""

    try:
        prop = Property.objects.select_related('owner').get(pk=data['property_id'])
    except Property.DoesNotExist as exc:
        raise NotFoundError('Property not found.') from exc

    if not prop.published or prop.listing_status != ListingStatus.PUBLISHED:
        raise UnpublishedError('This property is not published.')

    linked_flat = None
    if prop.type == PropertyType.APARTMENT:
        from listings.services.inventory import apartment_is_bookable, linked_apartment_flat

        linked_flat = linked_apartment_flat(prop)
        if not apartment_is_bookable(prop):
            raise UnavailableError(
                'This apartment is not free to book. It needs one vacant flat linked to the listing.',
            )
    elif not prop.available:
        raise UnavailableError('This property is not available for booking.')

    conflict = PropertyBooking.objects.filter(
        property=prop,
        renter=user,
        status__in=ACTIVE_STATUSES,
        is_deleted=False,
    ).exists()
    if conflict:
        raise ConflictError('You already have an active booking for this property.')

    if prop.owner_id == user.id:
        raise InvalidError('You cannot book your own listing.')

    duration = data.get('duration') or 1
    rent = Decimal(prop.rent)
    deposit = rent * Decimal(prop.deposit_months or 1)
    total_amount = rent * Decimal(duration) + deposit

    now = timezone.now()
    if prop.instant_book:
        status = BookingStatus.APPROVED
        booking_mode = BookingMode.INSTANT
        approved_at = now
    else:
        status = BookingStatus.PENDING
        booking_mode = BookingMode.REQUEST
        approved_at = None

    owner = prop.owner
    booking = PropertyBooking.objects.create(
        property=prop,
        renter=user,
        owner=owner,
        property_name=prop.name,
        property_type=prop.type,
        property_address=prop.address,
        property_image=_property_image(prop),
        renter_name=_display_name(user),
        renter_phone=user.phone,
        renter_email=user.email or '',
        owner_name=_display_name(owner),
        owner_phone=owner.phone,
        status=status,
        booking_mode=booking_mode,
        move_in_date=data.get('move_in_date'),
        move_out_date=data.get('move_out_date'),
        duration=duration,
        rent=rent,
        deposit=deposit,
        total_amount=total_amount,
        message=(data.get('message') or '').strip(),
        special_requests=(data.get('special_requests') or '').strip(),
        approved_at=approved_at,
    )

    if status == BookingStatus.APPROVED and linked_flat is not None:
        _assign_flat_to_booking(booking, linked_flat.id, actor=owner)

    from bookings.services.notify import schedule_booking_notice

    schedule_booking_notice(
        booking.id,
        'instant' if status == BookingStatus.APPROVED else 'requested',
    )
    return booking


def _assign_flat_to_booking(booking: PropertyBooking, flat_id, *, actor) -> None:
    """Occupy a flat and create tenancy from an approved/approving booking."""
    from portfolio.models import Flat, FlatStatus, Tenancy, TenancyStatus
    from listings.services.inventory import sync_flat_listing

    try:
        flat = Flat.objects.select_for_update().select_related('building').get(pk=flat_id)
    except Flat.DoesNotExist as exc:
        raise NotFoundError('Flat not found.') from exc

    if flat.building.owner_id != booking.owner_id and getattr(actor, 'role', None) != 'admin':
        raise ForbiddenError('You can only assign flats from your buildings.')

    if flat.status == FlatStatus.OCCUPIED:
        raise InvalidError('Flat is already occupied. Vacate first.')

    if flat.listing_id and str(flat.listing_id) != str(booking.property_id):
        raise InvalidError('This flat is linked to a different listing.')

    if flat.listing_id is None:
        flat.listing_id = booking.property_id

    Tenancy.objects.filter(flat=flat, status=TenancyStatus.ACTIVE).update(
        status=TenancyStatus.ENDED,
        end_date=timezone.localdate(),
    )

    start = booking.move_in_date or timezone.localdate()
    renter = booking.renter
    Tenancy.objects.create(
        flat=flat,
        tenant=renter,
        start_date=start,
        end_date=booking.move_out_date,
        deposit=booking.deposit,
        status=TenancyStatus.ACTIVE,
        notes=f'Created from booking {booking.id}',
        tenant_name=booking.renter_name or _display_name(renter),
        tenant_phone=booking.renter_phone or renter.phone,
        tenant_whatsapp=getattr(renter, 'whatsapp_number', '') or '',
        tenant_email=booking.renter_email or renter.email or '',
        tenant_nid='',
        tenant_address='',
    )
    flat.status = FlatStatus.OCCUPIED
    flat.save(update_fields=['status', 'listing_id', 'updated_at'])
    flat.building.refresh_counts()
    booking.flat = flat
    sync_flat_listing(flat)


@transaction.atomic
def patch_status(
    actor,
    booking_id,
    status: str,
    reason: str | None = None,
    flat_id=None,
) -> PropertyBooking:
    try:
        booking = PropertyBooking.objects.select_related(
            'renter',
            'owner',
            'property',
        ).get(
            pk=booking_id,
            is_deleted=False,
        )
    except PropertyBooking.DoesNotExist as exc:
        raise NotFoundError('Booking not found.') from exc

    is_admin = getattr(actor, 'role', None) == 'admin'
    is_owner = booking.owner_id == actor.id
    is_renter = booking.renter_id == actor.id
    now = timezone.now()
    reason = (reason or '').strip()

    if status == BookingStatus.APPROVED:
        if booking.status != BookingStatus.PENDING:
            raise InvalidStateError('Only pending bookings can be approved.')
        if not (is_owner or is_admin):
            raise ForbiddenError('Only the owner can approve bookings.')

        # Apartment bookings occupy the one flat linked to the listing.
        if booking.property_type == PropertyType.APARTMENT:
            from listings.services.inventory import linked_apartment_flat
            from portfolio.models import FlatStatus

            linked = linked_apartment_flat(booking.property)
            if linked is None or linked.status != FlatStatus.AVAILABLE:
                raise InvalidError(
                    'This listing is not linked to a vacant flat. Attach one in My listings before approving.',
                )
            _assign_flat_to_booking(booking, linked.id, actor=actor)

        booking.status = BookingStatus.APPROVED
        booking.approved_at = now
        update_fields = ['status', 'approved_at', 'updated_at']
        if booking.flat_id:
            update_fields.append('flat')
        booking.save(update_fields=update_fields)
        from bookings.services.notify import schedule_booking_notice

        schedule_booking_notice(booking.id, 'accepted')
        return booking

    if status == BookingStatus.REJECTED:
        if booking.status != BookingStatus.PENDING:
            raise InvalidStateError('Only pending bookings can be rejected.')
        if not (is_owner or is_admin):
            raise ForbiddenError('Only the owner can reject bookings.')
        if not reason:
            raise ReasonRequiredError('Rejection reason is required.')
        booking.status = BookingStatus.REJECTED
        booking.rejected_at = now
        booking.rejection_reason = reason
        booking.save(
            update_fields=['status', 'rejected_at', 'rejection_reason', 'updated_at'],
        )
        from bookings.services.notify import schedule_booking_notice

        schedule_booking_notice(booking.id, 'rejected', reason)
        return booking

    if status == BookingStatus.CANCELLED:
        if booking.status not in (BookingStatus.PENDING, BookingStatus.APPROVED):
            raise InvalidStateError('Only pending or approved bookings can be cancelled.')
        if not (is_renter or is_owner or is_admin):
            raise ForbiddenError('You cannot cancel this booking.')
        if not reason:
            raise ReasonRequiredError('Cancellation reason is required.')
        was_approved = booking.status == BookingStatus.APPROVED
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = now
        booking.cancellation_reason = reason
        booking.save(
            update_fields=[
                'status',
                'cancelled_at',
                'cancellation_reason',
                'updated_at',
            ],
        )
        if was_approved:
            from listings.services.inventory import release_booking_occupancy

            release_booking_occupancy(booking)
        return booking

    if status == BookingStatus.COMPLETED:
        if booking.status != BookingStatus.APPROVED:
            raise InvalidStateError('Only approved bookings can be completed.')
        if not (is_owner or is_admin):
            raise ForbiddenError('Only the owner can complete bookings.')
        booking.status = BookingStatus.COMPLETED
        booking.completed_at = now
        booking.save(update_fields=['status', 'completed_at', 'updated_at'])
        from listings.services.inventory import release_booking_occupancy

        release_booking_occupancy(booking)
        return booking

    raise InvalidStateError(f'Unsupported status: {status}')
