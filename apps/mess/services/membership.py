"""Link mess member rows to login accounts by phone."""

from __future__ import annotations

from django.db.models import Q

from accounts.phone import normalize_bd_phone, phone_lookup_variants
from core.exceptions import InvalidError
from mess.models import MessStudent
from mess.services.identity import promote_member_photo_to_user


def membership_phone_q(user_phone: str | None) -> Q:
    variants = phone_lookup_variants(user_phone)
    if not variants:
        return Q(pk__in=[])
    return Q(phone__in=variants) | Q(whatsapp_number__in=variants)


def link_user_to_mess_memberships(user) -> int:
    """
    Attach mess member records that share this account's phone.

    - Matches ``01…`` and ``+880…`` forms
    - Normalizes stored member phones to E.164
    - Relinks rows wrongly attached to another account whose phone does not match
    """
    variants = phone_lookup_variants(getattr(user, 'phone', None))
    if not variants:
        return 0

    qs = (
        MessStudent.objects.filter(is_deleted=False)
        .filter(membership_phone_q(user.phone))
        .select_related('user')
    )
    changed = 0
    for student in qs:
        updates: list[str] = []
        try:
            canonical = normalize_bd_phone(student.phone)
        except InvalidError:
            canonical = (getattr(user, 'phone', None) or student.phone).strip()

        if student.phone != canonical:
            student.phone = canonical
            updates.append('phone')

        if student.whatsapp_number:
            try:
                wa = normalize_bd_phone(student.whatsapp_number)
            except InvalidError:
                wa = student.whatsapp_number
            if wa != student.whatsapp_number:
                student.whatsapp_number = wa
                updates.append('whatsapp_number')

        should_claim = student.user_id is None
        if student.user_id and student.user_id != user.id:
            other_variants = phone_lookup_variants(
                getattr(student.user, 'phone', None),
            )
            # Linked account does not own this phone → reclaim for the real user.
            if not (other_variants & variants):
                should_claim = True

        if should_claim and student.user_id != user.id:
            student.user = user
            updates.append('user')
            if student.name and not (getattr(user, 'name', None) or '').strip():
                user.name = student.name
                user.save(update_fields=['name', 'updated_at'])
            promote_member_photo_to_user(student, user)

        if updates:
            student.save(update_fields=[*updates, 'updated_at'])
            changed += 1
    return changed
