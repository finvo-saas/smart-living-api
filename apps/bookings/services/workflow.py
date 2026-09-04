from decimal import Decimal

from django.utils import timezone

from bookings.models import BookingMode, BookingStatus, PropertyBooking
from core.exceptions import (
    ConflictError,
    ForbiddenError,
    InvalidStateError,
    NotFoundError,
    ReasonRequiredError,
    UnavailableError,
    UnpublishedError,
)
from listings.models import ListingStatus, Property


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


def create_booking(user, data: dict) -> PropertyBooking:
    from django.conf import settings

    if getattr(settings, 'CIMS_ENFORCE_BOOKING', True):
        from accounts.models import Role, UserProfile

        if getattr(user, 'role', None) in (Role.RENTER, Role.OWNER, 'renter', 'owner'):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if not profile.cims_registered:
                raise ForbiddenError(
                    'CIMS registration is required before booking. '
                    'Complete CIMS details in Profile (DMP compliance).',
                    code='CIMS_REQUIRED',
                )

    try:
        prop = Property.objects.select_related('owner').get(pk=data['property_id'])
    except Property.DoesNotExist as exc:
        raise NotFoundError('Property not found.') from exc

    if not prop.available:
        raise UnavailableError('This property is not available for booking.')

    if not prop.published or prop.listing_status != ListingStatus.PUBLISHED:
        raise UnpublishedError('This property is not published.')

    conflict = PropertyBooking.objects.filter(
        property=prop,
        renter=user,
        status__in=ACTIVE_STATUSES,
        is_deleted=False,
    ).exists()
    if conflict:
        raise ConflictError('You already have an active booking for this property.')

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
    return PropertyBooking.objects.create(
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


def patch_status(actor, booking_id, status: str, reason: str | None = None) -> PropertyBooking:
    try:
        booking = PropertyBooking.objects.select_related('renter', 'owner').get(
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
        booking.status = BookingStatus.APPROVED
        booking.approved_at = now
        booking.save(update_fields=['status', 'approved_at', 'updated_at'])
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
        return booking

    if status == BookingStatus.CANCELLED:
        if booking.status not in (BookingStatus.PENDING, BookingStatus.APPROVED):
            raise InvalidStateError('Only pending or approved bookings can be cancelled.')
        if not (is_renter or is_owner or is_admin):
            raise ForbiddenError('You cannot cancel this booking.')
        if not reason:
            raise ReasonRequiredError('Cancellation reason is required.')
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
        return booking

    if status == BookingStatus.COMPLETED:
        if booking.status != BookingStatus.APPROVED:
            raise InvalidStateError('Only approved bookings can be completed.')
        if not (is_owner or is_admin):
            raise ForbiddenError('Only the owner can complete bookings.')
        booking.status = BookingStatus.COMPLETED
        booking.completed_at = now
        booking.save(update_fields=['status', 'completed_at', 'updated_at'])
        return booking

    raise InvalidStateError(f'Unsupported status: {status}')
