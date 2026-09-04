"""Bangladesh university catalog for SEO landing pages."""
from __future__ import annotations

UNIVERSITIES = [
    {
        'slug': 'buet',
        'name': 'BUET',
        'fullName': 'Bangladesh University of Engineering and Technology',
        'city': 'Dhaka',
        'areas': ['Azimpur', 'Nilkhet', 'Dhanmondi', 'Shahbag', 'Lalbagh'],
        'lat': 23.7263,
        'lng': 90.3925,
    },
    {
        'slug': 'du',
        'name': 'Dhaka University',
        'fullName': 'University of Dhaka',
        'city': 'Dhaka',
        'areas': ['Shahbag', 'Nilkhet', 'Azimpur', 'New Market', 'Katabon'],
        'lat': 23.7330,
        'lng': 90.3928,
    },
    {
        'slug': 'nsu',
        'name': 'NSU',
        'fullName': 'North South University',
        'city': 'Dhaka',
        'areas': ['Bashundhara', 'Kuril', 'Vatara', 'Baridhara'],
        'lat': 23.8151,
        'lng': 90.4255,
    },
    {
        'slug': 'brac',
        'name': 'BRAC University',
        'fullName': 'BRAC University',
        'city': 'Dhaka',
        'areas': ['Merul Badda', 'Rampura', 'Badda', 'Mohakhali'],
        'lat': 23.7806,
        'lng': 90.4071,
    },
    {
        'slug': 'aiub',
        'name': 'AIUB',
        'fullName': 'American International University-Bangladesh',
        'city': 'Dhaka',
        'areas': ['Kuratoli', 'Kuril', 'Khilkhet', 'Nikunja'],
        'lat': 23.8213,
        'lng': 90.4275,
    },
    {
        'slug': 'iut',
        'name': 'IUT',
        'fullName': 'Islamic University of Technology',
        'city': 'Gazipur',
        'areas': ['Board Bazar', 'Gazipur', 'Tongi'],
        'lat': 23.9481,
        'lng': 90.3795,
    },
    {
        'slug': 'cuet',
        'name': 'CUET',
        'fullName': 'Chittagong University of Engineering & Technology',
        'city': 'Chittagong',
        'areas': ['Pahartali', 'Raozan', 'Kaptai Road'],
        'lat': 22.4619,
        'lng': 91.9695,
    },
    {
        'slug': 'ruet',
        'name': 'RUET',
        'fullName': 'Rajshahi University of Engineering & Technology',
        'city': 'Rajshahi',
        'areas': ['Kazla', 'Talaimari', 'Rajshahi'],
        'lat': 24.3636,
        'lng': 88.6284,
    },
]


def get_university(slug: str) -> dict | None:
    key = (slug or '').strip().lower()
    for uni in UNIVERSITIES:
        if uni['slug'] == key:
            return uni
    return None


def list_universities() -> list[dict]:
    return list(UNIVERSITIES)


def listings_near_university(slug: str, category: str = 'mess', limit: int = 24):
    uni = get_university(slug)
    if not uni:
        return None, []
    from listings.models import ListingStatus, Property

    qs = Property.objects.filter(
        published=True,
        listing_status=ListingStatus.PUBLISHED,
        flagged_unavailable_at__isnull=True,
        city__iexact=uni['city'],
    )
    if category and category != 'all':
        if category == 'mess':
            qs = qs.filter(type__in=['mess', 'hostel'])
        else:
            qs = qs.filter(type=category)
    area_q = None
    from django.db.models import Q

    for area in uni['areas']:
        clause = Q(area__icontains=area) | Q(address__icontains=area) | Q(name__icontains=area)
        area_q = clause if area_q is None else (area_q | clause)
    if area_q is not None:
        preferred = list(qs.filter(area_q).order_by('-featured', '-created_at')[:limit])
        if preferred:
            return uni, preferred
    return uni, list(qs.order_by('-featured', '-created_at')[:limit])
