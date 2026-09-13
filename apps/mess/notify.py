"""Mess living alerts: hisab, menu, and house rules."""
from __future__ import annotations

import logging

from django.db import transaction

from messaging.models import NotificationType

logger = logging.getLogger(__name__)

STUDENT_URL = '/mess/student-dashboard'


def schedule_hisab_closed(mess_id, year: int, month: int) -> None:
    transaction.on_commit(
        lambda mid=mess_id, y=year, m=month: notify_hisab_closed(mid, y, m),
    )


def notify_hisab_closed(mess_id, year: int, month: int) -> None:
    from mess.models import MemberMonthBill, MonthCloseStatus

    rows = (
        MemberMonthBill.objects.filter(
            month_close__mess_id=mess_id,
            month_close__year=year,
            month_close__month=month,
            month_close__status=MonthCloseStatus.CLOSED,
        )
        .select_related('student', 'student__user', 'month_close', 'month_close__mess')
    )
    for row in rows:
        student = row.student
        if student is None or not student.user_id:
            continue
        mess_name = row.month_close.mess.name if row.month_close_id else 'your mess'
        due = float(row.due or 0)
        if due > 0:
            body = (
                f'{mess_name} closed {month}/{year}. '
                f'Your due is ৳{due:,.0f}.'
            )
        else:
            body = f'{mess_name} closed {month}/{year}. You have no due this month.'
        _send(
            student.user,
            title='Mess hisab closed',
            body=body,
            tag=f'hisab-{mess_id}-{year}-{month}-{student.id}',
        )


def schedule_menu_published(mess_id, label: str) -> None:
    transaction.on_commit(
        lambda mid=mess_id, text=label: notify_active_students(
            mid,
            title='New mess menu',
            body=text,
            tag=f'menu-{mid}-{text[:40]}',
        ),
    )


def schedule_rule_violation(violation_id) -> None:
    transaction.on_commit(lambda vid=violation_id: notify_rule_violation(vid))


def notify_rule_violation(violation_id) -> None:
    from mess.models import RuleViolation

    row = (
        RuleViolation.objects.filter(pk=violation_id)
        .select_related('student', 'student__user', 'mess', 'rule')
        .first()
    )
    if row is None or row.student_id is None or not row.student.user_id:
        return
    rule = row.rule_title or (row.rule.title if row.rule_id else 'a house rule')
    place = row.mess.name if row.mess_id else 'your mess'
    body = f'{place}: {rule}.'
    if row.description:
        excerpt = ' '.join(row.description.split())
        if len(excerpt) > 140:
            excerpt = excerpt[:139].rstrip() + '…'
        body = f'{body} {excerpt}'
    _send(
        row.student.user,
        title='House rule notice',
        body=body,
        tag=f'rule-{row.id}',
    )


def notify_active_students(mess_id, *, title: str, body: str, tag: str) -> None:
    from mess.models import MessStudent

    students = MessStudent.objects.filter(
        mess_id=mess_id,
        is_active=True,
        is_deleted=False,
        user__isnull=False,
    ).select_related('user')
    seen = set()
    for student in students:
        if student.user_id in seen:
            continue
        seen.add(student.user_id)
        _send(student.user, title=title, body=body, tag=tag)


def _send(user, *, title: str, body: str, tag: str) -> None:
    from accounts.services.email import notify_channels

    if user is None:
        return
    try:
        notify_channels(
            user,
            title=title[:255],
            body=body,
            url=STUDENT_URL,
            ntype=NotificationType.SYSTEM,
            tag=tag[:80],
        )
    except Exception:
        logger.exception('Mess notice failed tag=%s user=%s', tag, getattr(user, 'id', None))
