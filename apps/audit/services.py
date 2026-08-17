"""Audit log creation and rollback helpers."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from accounts.models import Role, User
from audit.models import AuditAction, AuditEntityType, AuditLog
from listings.models import Property, PropertyType


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _client_user_agent(request) -> str:
    if request is None:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:512]


def create_audit_log(
    user: User | None,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    entity_name: str = '',
    changes: list | None = None,
    metadata: dict | None = None,
    rollback_data: dict | None = None,
    can_rollback: bool = False,
    ip_address: str | None = None,
    user_agent: str = '',
    request=None,
) -> AuditLog:
    if user is not None:
        user_name = user.name or user.phone
        user_role = user.role
    else:
        user_name = ''
        user_role = ''

    if request is not None:
        ip_address = ip_address or _client_ip(request)
        user_agent = user_agent or _client_user_agent(request)

    return AuditLog.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        entity_name=entity_name or str(entity_id),
        user=user,
        user_name=user_name,
        user_role=user_role,
        ip_address=ip_address,
        user_agent=user_agent,
        changes=changes or [],
        metadata=metadata or {},
        rollback_data=rollback_data,
        can_rollback=can_rollback,
    )


def _apply_property_rollback(data: dict[str, Any]) -> bool:
    try:
        prop = Property.objects.get(pk=data['entity_id'])
    except (Property.DoesNotExist, KeyError, ValueError):
        return False

    fields = data.get('fields') or {}
    update_fields = []
    for field, value in fields.items():
        if hasattr(prop, field):
            setattr(prop, field, value)
            update_fields.append(field)
    if update_fields:
        update_fields.append('updated_at')
        prop.save(update_fields=update_fields)
        return True
    return False


def _apply_user_rollback(data: dict[str, Any]) -> bool:
    try:
        user = User.objects.get(pk=data['entity_id'])
    except (User.DoesNotExist, KeyError, ValueError):
        return False

    fields = data.get('fields') or {}
    update_fields = []
    for field, value in fields.items():
        if hasattr(user, field):
            setattr(user, field, value)
            update_fields.append(field)
    if update_fields:
        update_fields.append('updated_at')
        user.save(update_fields=update_fields)
        return True
    return False


def _apply_user_moderation_rollback(data: dict[str, Any]) -> bool:
    from admin_api.models import UserModeration

    try:
        moderation = UserModeration.objects.get(user_id=data['entity_id'])
    except (UserModeration.DoesNotExist, KeyError, ValueError):
        return False

    status = (data.get('fields') or {}).get('status')
    if status is None:
        return False
    moderation.status = status
    moderation.save(update_fields=['status', 'updated_at'])
    if status == 'banned':
        User.objects.filter(pk=moderation.user_id).update(is_active=False)
    elif status in ('active', 'suspended'):
        User.objects.filter(pk=moderation.user_id).update(is_active=True)
    return True


def rollback_audit(log: AuditLog, actor: User, *, request=None) -> AuditLog:
    applied = False
    if log.can_rollback and log.rollback_data and not log.rolled_back:
        entity_type = log.rollback_data.get('entity_type') or log.entity_type
        if entity_type == AuditEntityType.PROPERTY:
            applied = _apply_property_rollback(log.rollback_data)
        elif entity_type == AuditEntityType.USER:
            applied = _apply_user_rollback(log.rollback_data)
            if not applied:
                applied = _apply_user_moderation_rollback(log.rollback_data)

    log.rolled_back = True
    log.save(update_fields=['rolled_back', 'updated_at'])

    create_audit_log(
        actor,
        action=AuditAction.ROLLBACK,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        entity_name=log.entity_name,
        metadata={
            'originalLogId': str(log.id),
            'rollbackApplied': applied,
            'rolledBackAt': timezone.now().isoformat(),
        },
        request=request,
    )
    return log
