"""SEO area catalog for /dhaka/dhanmondi/mess-style landings."""
from __future__ import annotations

AREA_PAGES = [
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'dhanmondi',
        'area': 'Dhanmondi',
        'aliases': ['dhanmondi', 'ধানমন্ডি'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'mohammadpur',
        'area': 'Mohammadpur',
        'aliases': ['mohammadpur', 'মোহাম্মদপুর'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'mirpur',
        'area': 'Mirpur',
        'aliases': ['mirpur', 'মিরপুর'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'uttara',
        'area': 'Uttara',
        'aliases': ['uttara', 'উত্তরা'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'bashundhara',
        'area': 'Bashundhara',
        'aliases': ['bashundhara', 'বসুন্ধরা'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'gulshan',
        'area': 'Gulshan',
        'aliases': ['gulshan', 'গুলশান'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'banani',
        'area': 'Banani',
        'aliases': ['banani', 'বনানী'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'motijheel',
        'area': 'Motijheel',
        'aliases': ['motijheel', 'মতিঝিল'],
    },
    {
        'citySlug': 'dhaka',
        'city': 'Dhaka',
        'areaSlug': 'farmgate',
        'area': 'Farmgate',
        'aliases': ['farmgate', 'ফার্মগেট'],
    },
    {
        'citySlug': 'chattogram',
        'city': 'Chattogram',
        'areaSlug': 'agrabad',
        'area': 'Agrabad',
        'aliases': ['agrabad'],
    },
    {
        'citySlug': 'sylhet',
        'city': 'Sylhet',
        'areaSlug': 'zindabazar',
        'area': 'Zindabazar',
        'aliases': ['zindabazar'],
    },
]


def list_area_pages() -> list[dict]:
    return [
        {
            'citySlug': a['citySlug'],
            'city': a['city'],
            'areaSlug': a['areaSlug'],
            'area': a['area'],
            'path': f"/{a['citySlug']}/{a['areaSlug']}/mess",
        }
        for a in AREA_PAGES
    ]


def get_area_page(city_slug: str, area_slug: str) -> dict | None:
    c = (city_slug or '').strip().lower()
    a = (area_slug or '').strip().lower()
    for row in AREA_PAGES:
        if row['citySlug'] == c and row['areaSlug'] == a:
            return row
    return None


def listings_for_area(city_slug: str, area_slug: str, category: str = 'mess', limit: int = 24):
    meta = get_area_page(city_slug, area_slug)
    if not meta:
        return None, []
    from django.db.models import Q

    from listings.models import ListingStatus, Property

    qs = Property.objects.filter(
        published=True,
        listing_status=ListingStatus.PUBLISHED,
        flagged_unavailable_at__isnull=True,
        city__iexact=meta['city'],
    )
    area_q = Q()
    for alias in meta['aliases']:
        area_q |= Q(area__icontains=alias)
    qs = qs.filter(area_q)
    if category in ('mess', 'hostel', 'apartment'):
        if category == 'mess':
            qs = qs.filter(type__in=('mess', 'hostel'))
        else:
            qs = qs.filter(type=category)
    return meta, list(qs.order_by('-featured', '-rating', '-created_at')[:limit])
