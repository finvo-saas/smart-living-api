"""Idempotent building helpers for seed commands."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Count

from portfolio.models import Building, Flat, Floor


@transaction.atomic
def ensure_building(*, owner, name: str, defaults: dict | None = None) -> tuple[Building, bool]:
    """
    Get or create a building for (owner, name).

    If duplicates exist (e.g. after ownership reassignment), keep the richest
    row (most flats, then oldest) and merge children from the extras.
    """
    defaults = dict(defaults or {})
    qs = (
        Building.objects.filter(owner=owner, name=name)
        .annotate(_flat_count=Count('flats'))
        .order_by('-_flat_count', 'created_at')
    )
    buildings = list(qs)
    if not buildings:
        building = Building.objects.create(owner=owner, name=name, **defaults)
        return building, True

    keep = buildings[0]
    for key, value in defaults.items():
        setattr(keep, key, value)
    keep.save()

    for dup in buildings[1:]:
        _merge_building_into(keep, dup)

    if hasattr(keep, 'refresh_counts'):
        keep.refresh_counts()
    return keep, False


@transaction.atomic
def consolidate_buildings_by_name(*, name: str, owner) -> Building | None:
    """
    Point every Building named ``name`` at ``owner``, then merge duplicates.
    """
    named = list(Building.objects.filter(name=name).order_by('created_at'))
    if not named:
        return None
    for b in named:
        if b.owner_id != owner.id:
            b.owner = owner
            b.save(update_fields=['owner', 'updated_at'])
    building, _ = ensure_building(owner=owner, name=name, defaults={})
    return building


def _merge_building_into(keep: Building, dup: Building) -> None:
    """Move floors/flats from dup → keep, then delete dup."""
    for floor in list(dup.floors.all()):
        keep_floor = keep.floors.filter(floor_number=floor.floor_number).first()
        if keep_floor is None:
            floor.building = keep
            floor.save(update_fields=['building', 'updated_at'])
            Flat.objects.filter(floor=floor).update(building=keep)
            continue

        for flat in list(floor.flats.all()):
            if keep.flats.filter(flat_number=flat.flat_number).exists():
                # Prefer keep's flat; drop the duplicate unit.
                flat.delete()
            else:
                flat.building = keep
                flat.floor = keep_floor
                flat.floor_number = keep_floor.floor_number
                flat.save(update_fields=['building', 'floor', 'floor_number', 'updated_at'])
        floor.delete()

    # Orphan flats (no floor) still on dup
    for flat in list(dup.flats.all()):
        if keep.flats.filter(flat_number=flat.flat_number).exists():
            flat.delete()
        else:
            flat.building = keep
            flat.save(update_fields=['building', 'updated_at'])

    # Shared scoped rows that still point at dup
    try:
        from ops.models import Notice
        from core.scope import ScopeType

        Notice.objects.filter(
            scope_type=ScopeType.BUILDING,
            scope_id=dup.id,
        ).update(scope_id=keep.id, scope_name=keep.name)
    except Exception:
        pass

    try:
        from support.models import Complaint

        Complaint.objects.filter(building=dup).update(building=keep)
        Complaint.objects.filter(
            scope_type='building',
            scope_id=dup.id,
        ).update(scope_id=keep.id, scope_name=keep.name)
    except Exception:
        pass

    try:
        from billing.models import Bill, BillTemplate, MeterReading, PropertyKind

        Bill.objects.filter(
            property_id=dup.id,
            property_type=PropertyKind.APARTMENT,
        ).update(property_id=keep.id, property_name=keep.name)
        BillTemplate.objects.filter(property_id=dup.id).update(property_id=keep.id)
        MeterReading.objects.filter(property_id=dup.id).update(property_id=keep.id)
    except Exception:
        pass

    try:
        from documents.models import Checklist, RentalAgreement

        RentalAgreement.objects.filter(property_id=dup.id).update(
            property_id=keep.id,
            scope_id=keep.id,
        )
        Checklist.objects.filter(property_id=dup.id).update(
            property_id=keep.id,
            scope_id=keep.id,
        )
    except Exception:
        pass

    dup.delete()
