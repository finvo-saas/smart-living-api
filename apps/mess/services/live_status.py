"""Mess live utilities status helpers."""
from __future__ import annotations

from django.utils import timezone

DEFAULT_LIVE_STATUS = {
    'water': 'ok',
    'electricity': 'ok',
    'wifi': 'ok',
    'breakfast': 'ok',
    'lunch': 'ok',
    'dinner': 'ok',
}

VALID_STATES = {'ok', 'warn', 'down'}


def normalize_live_status(raw: dict | None) -> dict:
    merged = dict(DEFAULT_LIVE_STATUS)
    if isinstance(raw, dict):
        for key, default in DEFAULT_LIVE_STATUS.items():
            value = str(raw.get(key, default)).lower()
            merged[key] = value if value in VALID_STATES else default
    return merged


def serialize_live_status(mess) -> dict:
    status = normalize_live_status(getattr(mess, 'live_status', None))
    updated = getattr(mess, 'live_status_updated_at', None)
    return {
        'status': status,
        'updatedAt': updated.isoformat() if updated else None,
    }


def update_live_status(mess, payload: dict) -> dict:
    current = normalize_live_status(mess.live_status)
    for key in DEFAULT_LIVE_STATUS:
        if key in payload:
            value = str(payload[key]).lower()
            if value in VALID_STATES:
                current[key] = value
    mess.live_status = current
    mess.live_status_updated_at = timezone.now()
    mess.save(update_fields=['live_status', 'live_status_updated_at', 'updated_at'])
    return serialize_live_status(mess)
