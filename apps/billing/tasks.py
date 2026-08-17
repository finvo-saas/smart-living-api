"""Background billing jobs (overdue marking, etc.)."""

from celery import shared_task
from django.utils import timezone

from billing.models import Bill, BillStatus


@shared_task(name='billing.mark_overdue_bills')
def mark_overdue_bills() -> dict:
    """Flip unpaid bills past due_date to overdue."""
    today = timezone.localdate()
    updated = (
        Bill.objects.filter(
            is_deleted=False,
            status=BillStatus.UNPAID,
            due_date__lt=today,
        ).update(status=BillStatus.OVERDUE)
    )
    return {'updated': updated, 'asOf': today.isoformat()}
