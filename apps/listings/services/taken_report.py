"""Visitor reports that a listing may already be taken.

A report notifies the owner. It does not close booking or hide the listing.
Only the owner confirming the report does that.
"""
from __future__ import annotations

from django.utils import timezone

from discovery.services.freshness import flag_unavailable
from listings.models import ListingTakenReport, Property, TakenReportStatus


def submit_taken_report(listing: Property, reporter=None) -> dict:
    user = reporter if getattr(reporter, 'is_authenticated', False) else None
    pending = ListingTakenReport.objects.filter(
        listing=listing,
        status=TakenReportStatus.PENDING,
    )
    if pending.exists():
        return _payload(listing, already=True)

    ListingTakenReport.objects.create(listing=listing, reporter=user)
    _notify_owner(listing)
    return _payload(listing, already=False)


def list_pending_for_owner(owner) -> list[dict]:
    rows = (
        ListingTakenReport.objects.filter(
            listing__owner=owner,
            status=TakenReportStatus.PENDING,
        )
        .select_related('listing')
        .order_by('-created_at')
    )
    return [_serialize(row) for row in rows]


def confirm_taken_report(owner, report_id) -> dict:
    report = _owned_pending(owner, report_id)
    flag_unavailable(report.listing)
    report.status = TakenReportStatus.CONFIRMED
    report.resolved_at = timezone.now()
    report.save(update_fields=['status', 'resolved_at', 'updated_at'])
    ListingTakenReport.objects.filter(
        listing=report.listing,
        status=TakenReportStatus.PENDING,
    ).exclude(pk=report.pk).update(
        status=TakenReportStatus.CONFIRMED,
        resolved_at=report.resolved_at,
    )
    return _serialize(report)


def dismiss_taken_report(owner, report_id) -> dict:
    report = _owned_pending(owner, report_id)
    report.status = TakenReportStatus.DISMISSED
    report.resolved_at = timezone.now()
    report.save(update_fields=['status', 'resolved_at', 'updated_at'])
    return _serialize(report)


def _owned_pending(owner, report_id) -> ListingTakenReport:
    from core.exceptions import ForbiddenError, NotFoundError

    try:
        report = ListingTakenReport.objects.select_related('listing').get(pk=report_id)
    except ListingTakenReport.DoesNotExist as exc:
        raise NotFoundError('Report not found.') from exc
    if report.listing.owner_id != owner.id and getattr(owner, 'role', None) != 'admin':
        raise ForbiddenError('Only the owner can respond to this report.')
    if report.status != TakenReportStatus.PENDING:
        from core.exceptions import InvalidStateError

        raise InvalidStateError('This report is already resolved.')
    return report


def _notify_owner(listing: Property) -> None:
    from messaging.services.push import create_in_app_notification

    create_in_app_notification(
        listing.owner,
        title='Someone says this may be taken',
        body=(
            f'{listing.name} was reported as already rented. '
            'Other renters can still see it until you confirm.'
        ),
        url='/my-properties/bookings',
        ntype='system',
    )


def _payload(listing: Property, *, already: bool) -> dict:
    return {
        'reported': True,
        'alreadyPending': already,
        'listingStillVisible': True,
        'id': str(listing.id),
    }


def _serialize(report: ListingTakenReport) -> dict:
    return {
        'id': str(report.id),
        'listingId': str(report.listing_id),
        'listingName': report.listing.name,
        'status': report.status,
        'createdAt': report.created_at.isoformat(),
    }
