"""Compatibility scoring for roommate lifestyle profiles."""
from __future__ import annotations

from accounts.models import RoommateProfile

SLEEP_ORDER = {
    RoommateProfile.SleepSchedule.EARLY: 0,
    RoommateProfile.SleepSchedule.NORMAL: 1,
    RoommateProfile.SleepSchedule.LATE: 2,
}
SOCIAL_ORDER = {
    RoommateProfile.Social.QUIET: 0,
    RoommateProfile.Social.BALANCED: 1,
    RoommateProfile.Social.CHATTY: 2,
}


def gender_compatible(me: RoommateProfile, other: RoommateProfile) -> bool:
    if me.gender_pref != RoommateProfile.GenderPref.ANY:
        if other.gender and other.gender != me.gender_pref:
            return False
    if other.gender_pref != RoommateProfile.GenderPref.ANY:
        if me.gender and me.gender != other.gender_pref:
            return False
    return True


def compatibility(me: RoommateProfile, other: RoommateProfile) -> dict:
    sleep = _ordered(SLEEP_ORDER, me.sleep_schedule, other.sleep_schedule, 20)
    smoking = 18 if me.smoking == other.smoking else 0
    cleanliness = round(16 * (1 - abs((me.cleanliness or 3) - (other.cleanliness or 3)) / 4))
    social = _ordered(SOCIAL_ORDER, me.social, other.social, 14)
    budget = _budget(me, other)
    city = 10 if _same_city(me, other) else 0
    cooking = 5 if me.cooking == other.cooking else 0
    pets = 5 if me.pets_ok == other.pets_ok else 0
    breakdown = [
        {'key': 'sleep', 'label': 'Sleep schedule', 'earned': sleep, 'max': 20},
        {'key': 'smoking', 'label': 'Smoking', 'earned': smoking, 'max': 18},
        {'key': 'cleanliness', 'label': 'Cleanliness', 'earned': cleanliness, 'max': 16},
        {'key': 'social', 'label': 'Social style', 'earned': social, 'max': 14},
        {'key': 'budget', 'label': 'Budget overlap', 'earned': budget, 'max': 12},
        {'key': 'city', 'label': 'Same city', 'earned': city, 'max': 10},
        {'key': 'cooking', 'label': 'Cooking', 'earned': cooking, 'max': 5},
        {'key': 'pets', 'label': 'Pets', 'earned': pets, 'max': 5},
    ]
    score = sum(item['earned'] for item in breakdown)
    return {'score': score, 'breakdown': breakdown}


def match_profiles(me: RoommateProfile, limit: int = 20) -> list[tuple[RoommateProfile, dict]]:
    qs = (
        RoommateProfile.objects.filter(looking=True)
        .exclude(user_id=me.user_id)
        .select_related('user')
    )
    if me.city:
        same_city = list(qs.filter(city__iexact=me.city.strip())[:80])
        others = list(qs.exclude(city__iexact=me.city.strip())[:40])
        candidates = same_city + others
    else:
        candidates = list(qs[:120])

    ranked = []
    for other in candidates:
        if not gender_compatible(me, other):
            continue
        payload = compatibility(me, other)
        ranked.append((other, payload))
    ranked.sort(key=lambda item: item[1]['score'], reverse=True)
    return ranked[:limit]


def _ordered(order: dict, a: str, b: str, max_points: int) -> int:
    if a == b:
        return max_points
    ia, ib = order.get(a), order.get(b)
    if ia is None or ib is None:
        return max_points // 2
    if abs(ia - ib) == 1:
        return max_points // 2
    return 0


def _budget(me: RoommateProfile, other: RoommateProfile) -> int:
    a_min, a_max = me.budget_min or 0, me.budget_max or 0
    b_min, b_max = other.budget_min or 0, other.budget_max or 0
    if not a_max and not b_max:
        return 12
    if not a_max:
        a_max = a_min or 10**9
    if not b_max:
        b_max = b_min or 10**9
    a_min = a_min or 0
    b_min = b_min or 0
    if a_min <= b_max and b_min <= a_max:
        return 12
    gap = min(abs(a_min - b_max), abs(b_min - a_max))
    if gap <= 3000:
        return 6
    return 0


def _same_city(me: RoommateProfile, other: RoommateProfile) -> bool:
    if not me.city or not other.city:
        return False
    return me.city.strip().lower() == other.city.strip().lower()
