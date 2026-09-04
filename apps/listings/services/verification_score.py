"""Composite 'Smart Verified' score for public listings."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from listings.models import Property, VerificationStatus


def verification_payload(prop: Property) -> dict:
    breakdown = _breakdown(prop)
    earned = sum(item['earned'] for item in breakdown)
    max_total = sum(item['max'] for item in breakdown)
    score = round(100 * earned / max_total) if max_total else 0
    if score >= 80:
        label = 'Smart Verified'
    elif score >= 55:
        label = 'Partially verified'
    else:
        label = 'Needs verification'
    return {
        'score': score,
        'label': label,
        'breakdown': breakdown,
        'signals': {
            'addressVerified': bool(getattr(prop, 'address_verified', False)),
            'photosVerified': bool(getattr(prop, 'photos_verified', False)),
            'rentVerified': bool(getattr(prop, 'rent_verified', False)),
            'listingVerified': bool(
                prop.verified or prop.verification_status == VerificationStatus.VERIFIED,
            ),
            'ownerNidVerified': _owner_nid_verified(prop),
        },
    }


def _breakdown(prop: Property) -> list[dict]:
    nid = _owner_nid_verified(prop)
    listing_verified = bool(
        prop.verified or prop.verification_status == VerificationStatus.VERIFIED,
    )
    photo_count = _photo_count(prop)
    has_geo = prop.latitude is not None and prop.longitude is not None
    desc_ok = len((prop.description or '').strip()) >= 80
    facilities_ok = len(prop.facilities or []) >= 3
    reviews_ok = (prop.review_count or 0) >= 1
    fresh = _is_fresh(prop)
    phone_ok = bool(getattr(prop.owner, 'is_phone_verified', False))
    address_ok = bool(getattr(prop, 'address_verified', False))
    photos_ok = bool(getattr(prop, 'photos_verified', False)) or photo_count >= 3
    rent_ok = bool(getattr(prop, 'rent_verified', False))

    return [
        _item('ownerNid', 'Owner NID verified', 15 if nid else 0, 15),
        _item('listingVerified', 'Listing verified by team', 12 if listing_verified else 0, 12),
        _item('addressVerified', 'Address verified', 12 if address_ok else (4 if has_geo else 0), 12),
        _item(
            'photosVerified',
            'Photos verified',
            12 if getattr(prop, 'photos_verified', False) else (6 if photo_count >= 3 else (3 if photo_count >= 1 else 0)),
            12,
        ),
        _item('rentVerified', 'Rent information verified', 12 if rent_ok else 0, 12),
        _item('location', 'Map coordinates', 8 if has_geo else 0, 8),
        _item('description', 'Complete description', 5 if desc_ok else 0, 5),
        _item('facilities', 'Facilities listed', 5 if facilities_ok else 0, 5),
        _item('reviews', 'Renter reviews', 9 if reviews_ok else 0, 9),
        _item('freshness', 'Confirmed in last 14 days', 6 if fresh else 0, 6),
        _item('ownerPhone', 'Owner phone verified', 4 if phone_ok else 0, 4),
    ]


def _item(key: str, label: str, earned: int, max_points: int) -> dict:
    return {
        'key': key,
        'label': label,
        'earned': earned,
        'max': max_points,
        'passed': earned >= max_points,
    }


def _owner_nid_verified(prop: Property) -> bool:
    cached = getattr(prop.owner, 'nid_verified_docs', None)
    if cached is not None:
        return bool(cached)
    from accounts.models import VerificationDocument

    return VerificationDocument.objects.filter(
        user_id=prop.owner_id,
        verification_type=VerificationDocument.VerificationType.NID,
        status=VerificationDocument.Status.VERIFIED,
    ).exists()


def _photo_count(prop: Property) -> int:
    urls = list(prop.image_urls or [])
    try:
        files = list(prop.image_files.all())
    except Exception:
        files = []
    return len(urls) + len(files)


def _is_fresh(prop: Property) -> bool:
    if not prop.last_confirmed_at:
        return False
    return prop.last_confirmed_at >= timezone.now() - timedelta(days=14)
