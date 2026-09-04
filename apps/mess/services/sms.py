"""Bulk SMS stub for mess notifications."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from accounts.services.sms import send_sms
from core.exceptions import InvalidError, NotFoundError
from mess.models import (
    Mess,
    MessStudent,
    SMSGroup,
    SMSMessage,
    SMSRecipientType,
    SMSStatus,
    SMSTemplate,
)

logger = logging.getLogger(__name__)


def _student_recipient(student: MessStudent) -> dict:
    return {
        'id': str(student.id),
        'name': student.name,
        'phone': student.phone,
        'studentId': student.student_id_code or None,
    }


def resolve_recipients(mess: Mess, data: dict) -> list[dict]:
    recipient_type = data.get('recipientType', SMSRecipientType.ALL)
    recipients = []

    if recipient_type == SMSRecipientType.ALL:
        students = MessStudent.objects.filter(
            mess=mess,
            is_active=True,
            is_deleted=False,
        )
        recipients = [_student_recipient(s) for s in students]

    elif recipient_type == SMSRecipientType.GROUP:
        group_id = data.get('groupId')
        if not group_id:
            raise InvalidError('groupId is required for group recipient type.')
        try:
            group = SMSGroup.objects.get(pk=group_id, mess=mess, is_deleted=False)
        except SMSGroup.DoesNotExist as exc:
            raise NotFoundError('SMS group not found.') from exc
        member_ids = group.member_ids or []
        students = MessStudent.objects.filter(
            pk__in=member_ids,
            mess=mess,
            is_active=True,
            is_deleted=False,
        )
        recipients = [_student_recipient(s) for s in students]

    elif recipient_type in (SMSRecipientType.INDIVIDUAL, SMSRecipientType.CUSTOM):
        student_ids = data.get('studentIds') or []
        students = MessStudent.objects.filter(
            pk__in=student_ids,
            mess=mess,
            is_active=True,
            is_deleted=False,
        )
        recipients = [_student_recipient(s) for s in students]

    return recipients


def send_bulk_sms(mess: Mess, user, data: dict) -> SMSMessage:
    content = data.get('content', '').strip()
    if not content:
        raise InvalidError('content is required.')

    template = None
    template_id = data.get('templateId')
    if template_id:
        try:
            template = SMSTemplate.objects.get(pk=template_id, is_deleted=False)
            if template.mess_id and template.mess_id != mess.id:
                raise NotFoundError('SMS template not found.')
        except SMSTemplate.DoesNotExist as exc:
            raise NotFoundError('SMS template not found.') from exc

    recipients = resolve_recipients(mess, data)
    total = len(recipients)
    successful = 0
    failed = 0

    message = SMSMessage.objects.create(
        mess=mess,
        template=template,
        content=content,
        recipient_type=data.get('recipientType', SMSRecipientType.ALL),
        recipients=recipients,
        total_recipients=total,
        status=SMSStatus.PENDING,
        sent_by=user,
        gateway=data.get('gateway', '') or getattr(settings, 'SMS_PROVIDER', 'console'),
        metadata=data.get('metadata', {}) or {},
    )

    for recipient in recipients:
        phone = recipient.get('phone', '')
        if not phone:
            failed += 1
            continue
        try:
            send_sms(phone, content)
            successful += 1
        except Exception as exc:
            logger.warning('SMS failed for %s: %s', phone, exc)
            failed += 1

    message.successful = successful
    message.failed = failed
    message.status = SMSStatus.SENT if successful > 0 else SMSStatus.FAILED
    message.sent_at = timezone.now()
    message.cost = Decimal('0.50') * successful
    if failed == total and total > 0:
        message.error_message = 'All recipients failed.'
    message.save()

    return message
