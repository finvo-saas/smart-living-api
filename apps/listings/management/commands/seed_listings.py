"""Seed sample published listings for Phase 2 discovery."""

from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User, UserProfile
from core.seed_catalog import EXTRA_LISTINGS
from listings.models import ListingStatus, Property, PropertyReview, VerificationStatus


SAMPLE = [
    {
        'key': 'green-valley',
        'name': 'Green Valley Mess',
        'type': 'mess',
        'rent': 3500,
        'area': 'Mirpur-10',
        'address': 'House 45, Road 7, Block C',
        'city': 'Dhaka',
        'latitude': 23.8067,
        'longitude': 90.3683,
        'gender': 'male',
        'seat_type': 'shared',
        'meal_included': True,
        'meal_plan': 'all',
        'meal_cost': 2000,
        'images': [
            'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800',
            'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800',
        ],
        'facilities': ['WiFi', 'AC', 'Generator', 'Security', 'Parking'],
        'nearby_facilities': ['Bus Stop', 'University', 'Hospital'],
        'building_age': 5,
        'floor_level': 2,
        'furnishing': 'furnished',
        'parking': True,
        'security': True,
        'verified': True,
        'featured': True,
        'description': (
            'Clean and spacious mess with modern amenities. '
            'Perfect for students and working professionals.'
        ),
        'owner_phone': '+8801712345678',
        'owner_name': 'Abdul Karim',
    },
    {
        'key': 'sunshine-apt',
        'name': 'Sunshine Apartment',
        'type': 'apartment',
        'rent': 15000,
        'area': 'Uttara',
        'address': 'Flat 4B, Building 12, Sector 7',
        'city': 'Dhaka',
        'latitude': 23.8744,
        'longitude': 90.3904,
        'gender': None,
        'images': [
            'https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800',
            'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800',
        ],
        'facilities': ['WiFi', 'AC', 'Lift', 'Security', 'Parking', 'Balcony'],
        'nearby_facilities': ['Metro Station', 'Shopping Mall', 'School'],
        'building_age': 8,
        'floor_level': 4,
        'furnishing': 'semi-furnished',
        'parking': True,
        'security': True,
        'verified': True,
        'deposit_months': 2,
        'description': (
            '2 BHK apartment in prime location. Well-maintained building '
            'with all modern facilities.'
        ),
        'owner_phone': '+8801712345679',
        'owner_name': 'Fatima Begum',
    },
    {
        'key': 'student-hub',
        'name': 'Student Hub Mess',
        'type': 'mess',
        'rent': 3200,
        'area': 'Dhanmondi',
        'address': 'House 23, Road 27',
        'city': 'Dhaka',
        'latitude': 23.7465,
        'longitude': 90.376,
        'gender': 'male',
        'seat_type': 'single',
        'meal_included': True,
        'meal_plan': 'lunch',
        'meal_cost': 1500,
        'images': [
            'https://images.unsplash.com/photo-1556912172-45b7abe8b7c8?w=800',
        ],
        'facilities': ['WiFi', 'Generator', 'Security', 'Common Kitchen'],
        'nearby_facilities': ['University', 'Bus Stop'],
        'building_age': 10,
        'floor_level': 1,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': False,
        'description': (
            'Affordable mess near universities with lunch included. '
            'Quiet study-friendly environment for students.'
        ),
        'owner_phone': '+8801712345680',
        'owner_name': 'Karim Hossain',
    },
    {
        'key': 'chittagong-hostel',
        'name': 'Hill View Hostel',
        'type': 'hostel',
        'rent': 4500,
        'area': 'Agrabad',
        'address': 'Road 5, Agrabad C/A',
        'city': 'Chittagong',
        'latitude': 22.3285,
        'longitude': 91.8123,
        'gender': 'female',
        'seat_type': 'shared',
        'meal_included': True,
        'meal_plan': 'all',
        'meal_cost': 1800,
        'images': [
            'https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800',
        ],
        'facilities': ['WiFi', 'Security', 'Laundry', 'CCTV'],
        'nearby_facilities': ['Bus Stop', 'Market'],
        'building_age': 3,
        'floor_level': 3,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': True,
        'description': (
            'Safe hostel for women near Agrabad with meals and laundry. '
            'Friendly management and 24/7 security.'
        ),
        'owner_phone': '+8801812345678',
        'owner_name': 'Nusrat Jahan',
    },
    {
        'key': 'sylhet-apt',
        'name': 'Tea Garden Apartment',
        'type': 'apartment',
        'rent': 12000,
        'area': 'Zindabazar',
        'address': 'Holding 18, Zindabazar',
        'city': 'Sylhet',
        'latitude': 24.8949,
        'longitude': 91.8687,
        'images': [
            'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800',
        ],
        'facilities': ['WiFi', 'Parking', 'Balcony'],
        'nearby_facilities': ['Shopping Mall', 'Hospital'],
        'building_age': 6,
        'floor_level': 2,
        'furnishing': 'unfurnished',
        'parking': True,
        'security': True,
        'verified': True,
        'deposit_months': 2,
        'instant_book': True,
        'description': (
            'Bright apartment in Zindabazar with balcony views. '
            'Ideal for small families relocating to Sylhet.'
        ),
        'owner_phone': '+8801912345678',
        'owner_name': 'Rafiq Ahmed',
    },
]

SAMPLE = SAMPLE + EXTRA_LISTINGS


class Command(BaseCommand):
    help = 'Seed sample properties and reviews for discovery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing seeded sample properties first',
        )

    def handle(self, *args, **options):
        if options['flush']:
            Property.objects.filter(name__in=[s['name'] for s in SAMPLE]).delete()

        created_count = 0
        for item in SAMPLE:
            owner, _ = User.objects.get_or_create(
                phone=item['owner_phone'],
                defaults={
                    'name': item['owner_name'],
                    'role': Role.OWNER,
                    'role_selected': True,
                    'is_phone_verified': True,
                },
            )
            if owner.role != Role.OWNER:
                owner.role = Role.OWNER
                owner.role_selected = True
                owner.name = owner.name or item['owner_name']
                owner.save()
            UserProfile.objects.get_or_create(user=owner)

            prop, created = Property.objects.update_or_create(
                owner=owner,
                name=item['name'],
                defaults={
                    'type': item['type'],
                    'rent': Decimal(item['rent']),
                    'area': item['area'],
                    'address': item['address'],
                    'city': item['city'],
                    'latitude': item.get('latitude'),
                    'longitude': item.get('longitude'),
                    'available': True,
                    'gender': item.get('gender'),
                    'seat_type': item.get('seat_type'),
                    'meal_included': item.get('meal_included'),
                    'meal_plan': item.get('meal_plan'),
                    'meal_cost': (
                        Decimal(item['meal_cost'])
                        if item.get('meal_cost') is not None
                        else None
                    ),
                    'image_urls': item.get('images') or [],
                    'videos': item.get('videos') or [],
                    'video_thumbnail': item.get('video_thumbnail', ''),
                    'facilities': item.get('facilities') or [],
                    'nearby_facilities': item.get('nearby_facilities') or [],
                    'building_age': item.get('building_age'),
                    'floor_level': item.get('floor_level'),
                    'furnishing': item.get('furnishing'),
                    'parking': item.get('parking'),
                    'security': item.get('security'),
                    'verified': item.get('verified', False),
                    'verification_status': (
                        VerificationStatus.VERIFIED
                        if item.get('verified')
                        else VerificationStatus.PENDING
                    ),
                    'verified_at': timezone.now() if item.get('verified') else None,
                    'description': item['description'],
                    'instant_book': item.get('instant_book', False),
                    'deposit_months': item.get(
                        'deposit_months',
                        2 if item['type'] == 'apartment' else 1,
                    ),
                    'published': True,
                    'listing_status': ListingStatus.PUBLISHED,
                    'featured': item.get('featured', False),
                    'featured_until': (
                        timezone.now() + timedelta(days=30)
                        if item.get('featured')
                        else None
                    ),
                },
            )
            if created:
                created_count += 1
            self.stdout.write(f'  {prop.name} → {prop.id}')

        # Reviews from several renters so discovery is not a single demo comment.
        reviewers = [
            ('+8801710000001', 5, 'Excellent mess with good food and friendly staff. Highly recommended for students.'),
            ('+8801710000002', 4, 'Clean apartment, lift works, generator during load shedding. Rent is fair for Banani.'),
            ('+8801710000004', 5, 'Safe ladies hostel. Management is strict about guests which I appreciate.'),
            ('+8801710000007', 4, 'GEC mess is noisy at night but food is home-style and location is unbeatable.'),
        ]
        published = list(Property.objects.filter(published=True).order_by('name'))
        for idx, (phone, rating, comment) in enumerate(reviewers):
            reviewer, _ = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'name': phone,
                    'role': Role.RENTER,
                    'role_selected': True,
                    'is_phone_verified': True,
                },
            )
            UserProfile.objects.get_or_create(user=reviewer)
            if not published:
                break
            prop = published[idx % len(published)]
            PropertyReview.objects.update_or_create(
                property=prop,
                user=reviewer,
                defaults={
                    'rating': rating,
                    'comment': comment,
                    'stay_duration_months': 4 + idx,
                    'verified_stay': True,
                },
            )
            prop.refresh_rating_cache()

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded listings complete ({created_count} new).',
            ),
        )
