"""Background reminder dispatch jobs."""

from celery import shared_task
from django.utils import timezone

from accounts.services.sms import send_sms
from reports.models import Reminder, ReminderStatus


@shared_task(name='reports.dispatch_due_reminders')
def dispatch_due_reminders() -> dict:
    """
    Mark due pending reminders as sent.
    Uses SMS console stub in development; real SMS when configured.
    """
    now = timezone.now()
    due = list(
        Reminder.objects.filter(
            status=ReminderStatus.PENDING,
            scheduled_date__lte=now,
        ).select_related('user')[:200],
    )
    sent = 0
    failed = 0
    for reminder in due:
        channels = reminder.channels or []
        try:
            if 'sms' in channels and reminder.user.phone:
                send_sms(reminder.user.phone, reminder.message)
            from accounts.services.email import notify_channels
            from messaging.models import NotificationType

            notify_channels(
                reminder.user,
                title=reminder.title or 'Reminder',
                body=reminder.message,
                url='/reminders',
                ntype=NotificationType.SYSTEM,
                tag=f'reminder-{reminder.id}',
            )
            reminder.status = ReminderStatus.SENT
            reminder.sent_date = now
            reminder.save(update_fields=['status', 'sent_date', 'updated_at'])
            sent += 1
        except Exception:  # noqa: BLE001 — isolate per-reminder failures
            reminder.status = ReminderStatus.FAILED
            reminder.save(update_fields=['status', 'updated_at'])
            failed += 1
    return {'sent': sent, 'failed': failed, 'checked': len(due)}
