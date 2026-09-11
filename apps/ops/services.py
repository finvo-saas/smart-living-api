"""Access helpers for unified ops.Notice."""

from __future__ import annotations

from django.db.models import Q

from accounts.models import Role
from core.scope import ScopeType
from hotels.models import Hotel, HotelBooking
from mess.models import Mess, MessStudent
from ops.models import Notice
from portfolio.models import Building, Flat, Tenancy, TenancyStatus


def resolve_scope_name(scope_type: str, scope_id) -> str:
    if scope_type == ScopeType.MESS:
        mess = Mess.objects.filter(pk=scope_id).first()
        return mess.name if mess else ''
    if scope_type == ScopeType.BUILDING:
        building = Building.objects.filter(pk=scope_id).first()
        return building.name if building else ''
    if scope_type == ScopeType.HOTEL:
        hotel = Hotel.objects.filter(pk=scope_id).first()
        return hotel.name if hotel else ''
    return ''


def owner_scope_ids(user) -> dict[str, set]:
    """Map scope_type → set of scope UUIDs owned by user."""
    return {
        ScopeType.MESS: set(
            Mess.objects.filter(owner=user, is_deleted=False).values_list('id', flat=True),
        ),
        ScopeType.BUILDING: set(
            Building.objects.filter(owner=user).values_list('id', flat=True),
        ),
        ScopeType.HOTEL: set(
            Hotel.objects.filter(owner=user, is_deleted=False).values_list(
                'id',
                flat=True,
            ),
        ),
    }


def member_scope_ids(user) -> dict[str, set]:
    """Scopes a renter/member can read."""
    mess_ids = set(
        MessStudent.objects.filter(
            user=user,
            is_active=True,
            is_deleted=False,
        ).values_list('mess_id', flat=True),
    )
    building_ids = set(
        Tenancy.objects.filter(
            tenant=user,
            status=TenancyStatus.ACTIVE,
        ).values_list('flat__building_id', flat=True),
    )
    hotel_ids = set(
        HotelBooking.objects.filter(user=user).values_list('hotel_id', flat=True),
    )
    return {
        ScopeType.MESS: mess_ids,
        ScopeType.BUILDING: building_ids,
        ScopeType.HOTEL: hotel_ids,
    }


def notices_visible_to(user):
    qs = Notice.objects.filter(is_deleted=False)
    if user.role == Role.ADMIN:
        return qs
    if user.role == Role.OWNER:
        owned = owner_scope_ids(user)
        q = Q(pk__in=[])  # empty
        for stype, ids in owned.items():
            if ids:
                q |= Q(scope_type=stype, scope_id__in=ids)
        return qs.filter(q)
    # renter / member
    scopes = member_scope_ids(user)
    q = Q(pk__in=[])
    for stype, ids in scopes.items():
        if ids:
            q |= Q(scope_type=stype, scope_id__in=ids)
    return qs.filter(q)


def can_manage_scope(user, scope_type: str, scope_id) -> bool:
    if user.role == Role.ADMIN:
        return True
    if user.role != Role.OWNER:
        return False
    owned = owner_scope_ids(user)
    return scope_id in owned.get(scope_type, set())


def can_read_notice(user, notice: Notice) -> bool:
    if user.role == Role.ADMIN:
        return True
    if can_manage_scope(user, notice.scope_type, notice.scope_id):
        return True
    scopes = member_scope_ids(user)
    if notice.scope_id not in scopes.get(notice.scope_type, set()):
        return False
    # Building flat targeting
    if notice.scope_type == ScopeType.BUILDING and notice.target_ids:
        my_flats = set(
            str(fid)
            for fid in Tenancy.objects.filter(
                tenant=user,
                status=TenancyStatus.ACTIVE,
                flat__building_id=notice.scope_id,
            ).values_list('flat_id', flat=True)
        )
        targets = {str(t) for t in notice.target_ids}
        return bool(my_flats & targets)
    return True


def assert_flat_targets_for_building(building_id, flat_ids: list[str]):
    if not flat_ids:
        return
    owned = set(
        str(fid)
        for fid in Flat.objects.filter(
            building_id=building_id,
            id__in=flat_ids,
        ).values_list('id', flat=True)
    )
    if set(flat_ids) - owned:
        from core.exceptions import InvalidError

        raise InvalidError('One or more flats do not belong to this building.')
