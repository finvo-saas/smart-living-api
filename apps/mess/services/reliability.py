"""Water / electricity reliability scores from profiles + live status."""
from __future__ import annotations

from mess.services.live_status import normalize_live_status

DEFAULT_WATER = {
    'availability': '24_7',  # 24_7 | limited | frequent_problem
    'source': 'wasa',
    'tankCapacityLiters': None,
    'hasFilter': False,
    'separateDrinkingWater': False,
    'hasBackup': False,
    # Owner freeform key → value notes (shown on public utilities card).
    'manual': {},
}

DEFAULT_ELECTRICITY = {
    'availability': '24_7',
    'loadSheddingLevel': 'rare',  # rare | moderate | frequent
    'hasIps': False,
    'hasGenerator': False,
    'generatorCovers': [],
    'liftBackup': False,
    'commonAreaBackup': False,
    'emergencyLight': False,
    'meterType': 'shared',
    'billSplitMethod': 'equal',
    'manual': {},
}

_AVAIL_BASE = {
    '24_7': 88,
    'limited': 62,
    'frequent_problem': 38,
}

_LIVE_ADJ = {'ok': 6, 'warn': -10, 'down': -22}


def _merge(defaults: dict, raw) -> dict:
    out = dict(defaults)
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key not in out:
                continue
            if key == 'manual' and isinstance(value, dict):
                cleaned = {}
                for mk, mv in value.items():
                    label = str(mk).strip()
                    if not label:
                        continue
                    cleaned[label] = '' if mv is None else str(mv)
                out[key] = cleaned
            else:
                out[key] = value
    return out


def water_profile_for(mess) -> dict:
    return _merge(DEFAULT_WATER, mess.water_profile)


def electricity_profile_for(mess) -> dict:
    return _merge(DEFAULT_ELECTRICITY, mess.electricity_profile)


def _score_from_profile(availability: str, bonuses: list[bool], live_key: str, mess) -> int:
    score = _AVAIL_BASE.get(str(availability or 'limited'), 62)
    for hit in bonuses:
        if hit:
            score += 3
    live = normalize_live_status(mess.live_status or {})
    score += _LIVE_ADJ.get(live.get(live_key, 'ok'), 0)
    return max(0, min(100, int(round(score))))


def water_reliability(mess) -> dict:
    profile = water_profile_for(mess)
    score = _score_from_profile(
        profile.get('availability'),
        [
            bool(profile.get('hasFilter')),
            bool(profile.get('separateDrinkingWater')),
            bool(profile.get('hasBackup')),
            bool(profile.get('tankCapacityLiters')),
        ],
        'water',
        mess,
    )
    return {
        'score': score,
        'label': _label(score),
        'profile': profile,
        'live': normalize_live_status(mess.live_status or {}).get('water', 'ok'),
    }


def electricity_reliability(mess) -> dict:
    profile = electricity_profile_for(mess)
    shedding = str(profile.get('loadSheddingLevel') or 'rare')
    shedding_penalty = {'rare': 0, 'moderate': -8, 'frequent': -18}.get(shedding, -4)
    score = _score_from_profile(
        profile.get('availability'),
        [
            bool(profile.get('hasIps')),
            bool(profile.get('hasGenerator')),
            bool(profile.get('commonAreaBackup')),
            bool(profile.get('emergencyLight')),
            bool(profile.get('liftBackup')),
        ],
        'electricity',
        mess,
    )
    score = max(0, min(100, score + shedding_penalty))
    return {
        'score': score,
        'label': _label(score),
        'profile': profile,
        'live': normalize_live_status(mess.live_status or {}).get('electricity', 'ok'),
    }


def reliability_bundle(mess) -> dict:
    water = water_reliability(mess)
    electric = electricity_reliability(mess)
    return {
        'water': water,
        'electricity': electric,
        'combined': round((water['score'] + electric['score']) / 2),
    }


def _label(score: int) -> str:
    if score >= 90:
        return 'Excellent'
    if score >= 75:
        return 'Reliable'
    if score >= 55:
        return 'Average'
    return 'Unreliable'
