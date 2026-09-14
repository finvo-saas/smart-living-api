"""Create and resize a building's floors and flats from a per-floor plan."""

from django.db import transaction

from core.exceptions import InvalidError
from portfolio.models import Building, Flat, FlatStatus, Floor
from subscriptions.services import get_flat_limit_status


def _protected_reason(flat: Flat) -> str | None:
    if flat.status != FlatStatus.AVAILABLE:
        return 'occupied or under maintenance'
    if flat.listing_id:
        return 'linked to a listing'
    if flat.tenancies.all():
        return 'has rental history'
    return None


def _next_flat_number(floor_number: int, used: set[str]) -> str:
    prefix = str(floor_number)
    for index in range(26):
        candidate = f'{prefix}{chr(65 + index)}'
        if candidate not in used:
            return candidate
    extra = 1
    while True:
        candidate = f'{prefix}-{extra}'
        if candidate not in used:
            return candidate
        extra += 1


def _copy_rent(flats: list[Flat]):
    for flat in flats:
        if flat.rent and flat.rent > 0:
            return flat.rent
    return 0


def sync_building_layout(building: Building, layouts: list[dict]) -> Building:
    """
    Match floors and flats to layouts.

    Each item is ``{floor_number, flat_count}``. Occupied, listed, or
    previously rented flats are kept. Extra empty flats are removed.
    """
    wanted: dict[int, int] = {}
    for item in layouts:
        number = int(item['floor_number'])
        count = int(item['flat_count'])
        if number in wanted:
            raise InvalidError('Each floor number can only be set once.')
        if count < 0:
            raise InvalidError('Flat count cannot be negative.')
        wanted[number] = count

    if not wanted:
        raise InvalidError('Add at least one floor.')
    if sum(wanted.values()) < 1:
        raise InvalidError('Add at least one flat.')

    with transaction.atomic():
        building = Building.objects.select_for_update().get(pk=building.pk)
        floors = {
            floor.floor_number: floor
            for floor in Floor.objects.filter(building=building)
        }
        flats = list(
            Flat.objects.filter(building=building)
            .select_related('floor')
            .prefetch_related('tenancies'),
        )
        by_floor: dict[int, list[Flat]] = {}
        for flat in flats:
            by_floor.setdefault(flat.floor_number, []).append(flat)

        for number, floor_flats in by_floor.items():
            protected = sum(1 for flat in floor_flats if _protected_reason(flat))
            target = wanted.get(number, 0)
            if protected > target:
                raise InvalidError(
                    f'Floor {number} has {protected} flats that are occupied, '
                    f'listed, or have rental history. It cannot go below {protected}.',
                )

        owner = building.owner
        status_data = get_flat_limit_status(owner)
        plan_max = status_data['max']
        if plan_max >= 0:
            owner_used = Flat.objects.filter(building__owner=owner).count()
            projected = owner_used - len(flats) + sum(wanted.values())
            if projected > plan_max:
                raise InvalidError(
                    f'Plan allows up to {plan_max} flats. '
                    f'This change would use {projected}.',
                )

        used_numbers = {flat.flat_number for flat in flats}

        for number, floor_flats in list(by_floor.items()):
            if number in wanted:
                continue
            for flat in floor_flats:
                reason = _protected_reason(flat)
                if reason:
                    raise InvalidError(
                        f'Floor {number} still has a flat that cannot be removed '
                        f'({flat.flat_number} is {reason}).',
                    )
                used_numbers.discard(flat.flat_number)
                flat.delete()
            floor = floors.pop(number, None)
            if floor is not None:
                floor.delete()
            by_floor.pop(number, None)

        for number, target in wanted.items():
            floor = floors.get(number)
            if floor is None:
                floor = Floor.objects.create(
                    building=building,
                    floor_number=number,
                    name=f'Floor {number}',
                )
                floors[number] = floor

            current = list(by_floor.get(number, []))
            if len(current) > target:
                removable = [
                    flat for flat in current if not _protected_reason(flat)
                ]
                removable.sort(key=lambda flat: flat.flat_number, reverse=True)
                extra = len(current) - target
                for flat in removable[:extra]:
                    used_numbers.discard(flat.flat_number)
                    flat.delete()
                    current.remove(flat)

            rent = _copy_rent(current)
            while len(current) < target:
                number_label = _next_flat_number(number, used_numbers)
                used_numbers.add(number_label)
                created = Flat.objects.create(
                    building=building,
                    floor=floor,
                    floor_number=number,
                    flat_number=number_label,
                    rent=rent,
                    status=FlatStatus.AVAILABLE,
                )
                current.append(created)

            for flat in current:
                updates = []
                if flat.floor_id != floor.id:
                    flat.floor = floor
                    updates.append('floor')
                if flat.floor_number != number:
                    flat.floor_number = number
                    updates.append('floor_number')
                if updates:
                    flat.save(update_fields=updates + ['updated_at'])
            by_floor[number] = current

        building.refresh_counts()
    building.refresh_from_db()
    return building
