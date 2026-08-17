"""Assemble renter history payload for GET /renters/{id}/history/."""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from accounts.models import Role, User
from billing.models import Bill, BillStatus
from core.exceptions import ForbiddenError, NotFoundError
from payments.models import PaymentMethod
from portfolio.models import Tenancy, TenancyStatus
from support.models import Complaint, ComplaintStatus


def _iso_date(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _iso_dt(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        text = value.isoformat()
        if text.endswith('+00:00'):
            return text.replace('+00:00', 'Z')
        return text
    return str(value)


def _map_payment_method(method: str | None) -> str | None:
    if not method:
        return None
    mapping = {
        PaymentMethod.BKASH: 'bkash',
        PaymentMethod.NAGAD: 'nagad',
        PaymentMethod.CASH: 'cash',
        PaymentMethod.BANK_TRANSFER: 'bank',
        PaymentMethod.ROCKET: 'other',
        PaymentMethod.CARD: 'other',
    }
    return mapping.get(method, 'other')


def _map_bill_status(status: str) -> str:
    if status == BillStatus.PAID:
        return 'paid'
    if status == BillStatus.OVERDUE:
        return 'overdue'
    return 'pending'


def _map_tenancy_status(tenancy: Tenancy) -> str:
    if tenancy.status == TenancyStatus.ACTIVE:
        return 'ongoing'
    if tenancy.status == TenancyStatus.ENDED:
        if tenancy.end_date and tenancy.end_date < timezone.localdate():
            return 'completed'
        return 'terminated'
    return 'terminated'


def _map_complaint_status(status: str) -> str:
    if status == ComplaintStatus.IN_PROGRESS:
        return 'in_progress'
    if status == ComplaintStatus.RESOLVED:
        return 'resolved'
    return 'open'


def assert_can_view_renter_history(*, viewer: User, renter: User) -> None:
    if viewer.id == renter.id:
        return
    if viewer.role == Role.ADMIN:
        return
    if viewer.role == Role.OWNER and Tenancy.objects.filter(
        tenant=renter,
        flat__building__owner=viewer,
    ).exists():
        return
    raise ForbiddenError('You cannot view this renter history.')


def build_renter_history(renter: User) -> dict:
    tenancies = list(
        Tenancy.objects.filter(tenant=renter)
        .select_related('flat', 'flat__building', 'flat__building__owner')
        .order_by('-start_date'),
    )

    rental_histories = []
    for tenancy in tenancies:
        building = tenancy.flat.building
        owner = building.owner
        rental_histories.append(
            {
                'id': str(tenancy.id),
                'renterId': str(renter.id),
                'propertyId': str(building.id),
                'propertyName': building.name,
                'propertyAddress': building.address,
                'flatNumber': tenancy.flat.flat_number,
                'moveInDate': _iso_date(tenancy.start_date),
                'moveOutDate': _iso_date(tenancy.end_date),
                'monthlyRent': float(tenancy.flat.rent),
                'status': _map_tenancy_status(tenancy),
                'terminationReason': None,
                'ownerId': str(owner.id),
                'ownerName': owner.name or owner.phone,
                'ownerPhone': owner.phone,
            },
        )

    flat_ids = [t.flat_id for t in tenancies]
    bills = (
        Bill.objects.filter(is_deleted=False)
        .filter(Q(tenant=renter) | Q(flat_id__in=flat_ids))
        .select_related('flat')
        .prefetch_related('payment_transactions')
        .order_by('-year', '-created_at')
    )

    payment_histories = []
    for bill in bills:
        rental_id = None
        if bill.flat_id:
            for tenancy in tenancies:
                if tenancy.flat_id == bill.flat_id:
                    rental_id = str(tenancy.id)
                    break
        if rental_id is None and tenancies:
            rental_id = str(tenancies[0].id)

        txn = (
            bill.payment_transactions.filter(status='completed')
            .order_by('-completed_at')
            .first()
        )
        payment_histories.append(
            {
                'id': str(bill.id),
                'rentalHistoryId': rental_id or '',
                'month': bill.month,
                'year': bill.year,
                'amount': float(bill.amount),
                'status': _map_bill_status(bill.status),
                'paidDate': _iso_date(bill.paid_date),
                'dueDate': _iso_date(bill.due_date),
                'paymentMethod': _map_payment_method(
                    txn.payment_method if txn else None,
                ),
                'notes': txn.receipt_note if txn else None,
            },
        )

    complaints = Complaint.objects.filter(user=renter, is_deleted=False).order_by(
        '-created_at',
    )
    complaint_histories = []
    for complaint in complaints:
        rental_id = str(tenancies[0].id) if tenancies else ''
        complaint_histories.append(
            {
                'id': str(complaint.id),
                'rentalHistoryId': rental_id,
                'title': complaint.title,
                'description': complaint.description,
                'category': 'other',
                'status': _map_complaint_status(complaint.status),
                'createdAt': _iso_dt(complaint.created_at),
                'resolvedAt': _iso_dt(complaint.resolved_at),
                'resolution': complaint.response or None,
            },
        )

    resolved = sum(
        1
        for c in complaint_histories
        if c['status'] in ('resolved', 'closed')
    )

    return {
        'renterId': str(renter.id),
        'renterName': renter.name or renter.phone,
        'rentalHistories': rental_histories,
        'paymentHistories': payment_histories,
        'complaintHistories': complaint_histories,
        'ownerReferences': [],
        'ownerRatings': [],
        'totalRentals': len(rental_histories),
        'averageRating': 0.0,
        'totalComplaints': len(complaint_histories),
        'resolvedComplaints': resolved,
    }


def get_renter_history(*, viewer: User, renter_id) -> dict:
    try:
        renter = User.objects.get(pk=renter_id)
    except User.DoesNotExist as exc:
        raise NotFoundError('Renter not found.') from exc

    assert_can_view_renter_history(viewer=viewer, renter=renter)
    return build_renter_history(renter)
