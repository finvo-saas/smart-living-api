"""Background billing jobs (overdue marking, automation rules)."""

from celery import shared_task
from django.utils import timezone

from billing.models import Bill, BillStatus


@shared_task(name='billing.mark_overdue_bills')
def mark_overdue_bills() -> dict:
    """Flip unpaid bills past due_date to overdue."""
    today = timezone.localdate()
    due = Bill.objects.filter(
        is_deleted=False,
        status=BillStatus.UNPAID,
        due_date__lt=today,
    )
    bill_ids = list(due.values_list('id', flat=True))
    updated = due.update(status=BillStatus.OVERDUE)
    if bill_ids:
        from billing.notify import notify_bills_overdue

        notify_bills_overdue(bill_ids)
    return {'updated': updated, 'asOf': today.isoformat()}


@shared_task(name='billing.run_bill_generation_rules')
def run_bill_generation_rules() -> dict:
    """
    Execute due automation rules and create bills from their templates.

    Safe to run daily (or more often); each rule advances next_run after a cycle.
    """
    from billing.services.scheduler import run_due_bill_rules

    return run_due_bill_rules()
