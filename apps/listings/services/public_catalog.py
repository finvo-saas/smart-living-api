"""One public search result per place.

A mess and the listing synced from it, or a wizard listing and the listing
published from the same flat, must not both appear in search.
"""
from __future__ import annotations

from listings.models import Property, PropertyType


def _norm(value) -> str:
    return ' '.join((value or '').strip().lower().split())


def unique_public_listings(listings) -> list[Property]:
    """Keep the richest published listing for each place, in original order."""
    items = list(listings)
    if len(items) < 2:
        return items

    parent: dict[str, str] = {}

    def add(node: str) -> None:
        parent.setdefault(node, node)

    def find(node: str) -> str:
        add(node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for prop in items:
        node = f'id:{prop.id}'
        for key in (_place_key(prop), *_inventory_keys(prop)):
            union(node, key)

    groups: dict[str, list[Property]] = {}
    for prop in items:
        groups.setdefault(find(f'id:{prop.id}'), []).append(prop)

    drop = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        winner = max(group, key=_preference)
        drop.update(prop.id for prop in group if prop.id != winner.id)

    return [prop for prop in items if prop.id not in drop]


def _place_key(prop: Property) -> str:
    return '|'.join(
        (
            'place',
            str(prop.owner_id),
            prop.type,
            _norm(prop.name),
            _norm(prop.address),
        )
    )


def _inventory_keys(prop: Property) -> list[str]:
    keys = []
    if prop.type == PropertyType.APARTMENT:
        unit = _norm(prop.unit_number)
        if unit:
            keys.append(f'unit|{prop.owner_id}|{_norm(prop.address)}|{unit}')
        for flat in prop.linked_flats.all():
            address = _norm(getattr(flat.building, 'address', '') or prop.address)
            keys.append(f'flat|{flat.id}')
            keys.append(f'unit|{prop.owner_id}|{address}|{_norm(flat.flat_number)}')
    elif prop.type in (PropertyType.MESS, PropertyType.HOSTEL):
        for mess in prop.linked_messes.all():
            keys.append(f'mess|{mess.id}')
    return keys


def _preference(prop: Property) -> tuple:
    linked = prop.linked_flats.all() or prop.linked_messes.all()
    images = prop.image_files.all() if hasattr(prop, 'image_files') else []
    return (
        1 if linked else 0,
        len(images),
        prop.updated_at.timestamp() if prop.updated_at else 0,
    )
