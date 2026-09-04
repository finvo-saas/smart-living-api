"""Per-listing safety score for Bangladesh housing seekers."""
from __future__ import annotations

from listings.models import Property, VerificationStatus


def safety_score_for_property(prop: Property) -> dict:
    facilities = [str(f).lower() for f in (prop.facilities or [])]
    nearby = [str(f).lower() for f in (prop.nearby_facilities or [])]
    blob = ' '.join(facilities + nearby)

    items = [
        _item(
            'buildingSecurity',
            'Building security / guard',
            20 if prop.security or _has(blob, ('security', 'guard', 'gate', 'নিরাপত্তা')) else 0,
            20,
        ),
        _item(
            'cctv',
            'CCTV coverage',
            15 if (prop.cctv is True) or _has(blob, ('cctv', 'camera', 'সিসিটিভি')) else (8 if prop.cctv is False else 0),
            15,
        ),
        _item(
            'streetLighting',
            'Street lighting',
            10 if (prop.street_lighting is True) or _has(blob, ('light', 'lighting', 'রাস্তার আলো')) else 0,
            10,
        ),
        _item(
            'police',
            'Near police station / thana',
            15 if _has(blob, ('police', 'thana', 'থানা', 'পুলিশ')) else 0,
            15,
        ),
        _item(
            'hospital',
            'Emergency hospital / clinic nearby',
            15 if _has(blob, ('hospital', 'clinic', 'হাসপাতাল', 'ক্লিনিক')) else 0,
            15,
        ),
        _item(
            'transport',
            'Transport access',
            10 if _has(blob, ('bus', 'metro', 'station', 'cng', 'বাস', 'মেট্রো')) else 0,
            10,
        ),
        _item(
            'verified',
            'Verified listing / owner',
            15 if prop.verified or prop.verification_status == VerificationStatus.VERIFIED else 0,
            15,
        ),
    ]
    earned = sum(i['earned'] for i in items)
    max_total = sum(i['max'] for i in items) or 1
    score = round(100 * earned / max_total)
    if score >= 80:
        label = 'High safety'
    elif score >= 55:
        label = 'Moderate safety'
    else:
        label = 'Review safety carefully'
    return {'score': score, 'label': label, 'breakdown': items}


def _has(blob: str, keys: tuple[str, ...]) -> bool:
    return any(k in blob for k in keys)


def _item(key: str, label: str, earned: int, max_points: int) -> dict:
    return {
        'key': key,
        'label': label,
        'earned': earned,
        'max': max_points,
        'passed': earned >= max_points * 0.6,
    }
