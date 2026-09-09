"""Seed sample hotels and rooms for Phase 5."""

from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import Role, User, UserProfile
from core.seed_catalog import EXTRA_HOTELS
from hotels.models import DEFAULT_CANCELLATION, DEFAULT_PRICING_RULES, Hotel, Room


SEASONAL = [
    {
        'id': 'season-winter',
        'name': 'Peak winter',
        'startDate': '2024-12-15',
        'endDate': '2025-01-10',
        'multiplier': 1.3,
    },
    {
        'id': 'season-eid',
        'name': 'Eid holiday',
        'startDate': '2025-03-28',
        'endDate': '2025-04-05',
        'multiplier': 1.4,
    },
]

HOTELS = [
    {
        'name': 'Grand Plaza Hotel Dhaka',
        'type': 'hotel',
        'star_rating': 4,
        'address': '123 Main Street, Road 5',
        'area': 'Gulshan',
        'city': 'Dhaka',
        'latitude': 23.8103,
        'longitude': 90.4125,
        'images': [
            'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800',
            'https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800',
        ],
        'description': (
            'Luxury hotel in the heart of Gulshan with modern amenities and excellent service. '
            'Perfect for business and leisure travelers.'
        ),
        'amenities': [
            'WiFi', 'AC', 'Parking', 'Restaurant', 'Gym', 'Swimming Pool',
            'Spa', 'Room Service', 'Laundry',
        ],
        'check_in_time': '14:00',
        'check_out_time': '12:00',
        'minimum_stay': 1,
        'license_number': 'HTL-2024-001',
        'verified': True,
        'featured': True,
        'owner_phone': '+8801512345678',
        'rooms': [
            {'room_number': '101', 'type': 'double', 'floor': 1, 'capacity': 2, 'base_price': 4500},
            {'room_number': '201', 'type': 'suite', 'floor': 2, 'capacity': 3, 'base_price': 7500},
            {'room_number': '301', 'type': 'single', 'floor': 3, 'capacity': 1, 'base_price': 3500},
        ],
    },
    {
        'name': 'Comfort Guest House',
        'type': 'guest-house',
        'star_rating': 3,
        'address': '45 Park Avenue, Block C',
        'area': 'Dhanmondi',
        'city': 'Dhaka',
        'latitude': 23.7465,
        'longitude': 90.376,
        'images': [
            'https://images.unsplash.com/photo-1590490360182-c33d57733427?w=800',
        ],
        'description': (
            'Cozy guest house in Dhanmondi area. Affordable accommodation with clean rooms '
            'and friendly staff.'
        ),
        'amenities': ['WiFi', 'AC', 'Parking', 'Restaurant', 'Laundry'],
        'check_in_time': '13:00',
        'check_out_time': '11:00',
        'minimum_stay': 1,
        'verified': True,
        'featured': False,
        'owner_phone': '+8801912345678',
        'rooms': [
            {'room_number': 'A1', 'type': 'double', 'floor': 1, 'capacity': 2, 'base_price': 2200},
            {'room_number': 'A2', 'type': 'family', 'floor': 1, 'capacity': 4, 'base_price': 3200},
        ],
    },
]

HOTELS = HOTELS + EXTRA_HOTELS


class Command(BaseCommand):
    help = 'Seed sample hotels with rooms'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete existing seeded hotels first',
        )

    def handle(self, *args, **options):
        default_owner, _ = User.objects.get_or_create(
            phone='+8801512345678',
            defaults={
                'name': 'Tanvir Hasan',
                'role': Role.OWNER,
                'role_selected': True,
                'is_phone_verified': True,
            },
        )
        UserProfile.objects.get_or_create(user=default_owner)

        if options['flush']:
            Hotel.objects.filter(name__in=[h['name'] for h in HOTELS]).delete()

        pricing_rules = {
            **DEFAULT_PRICING_RULES,
            'seasonalRules': SEASONAL,
        }
        cancellation = dict(DEFAULT_CANCELLATION)

        for item in HOTELS:
            owner_phone = item.get('owner_phone', '+8801512345678')
            owner = User.objects.filter(phone=owner_phone).first() or default_owner
            UserProfile.objects.get_or_create(user=owner)
            hotel, _ = Hotel.objects.update_or_create(
                owner=owner,
                name=item['name'],
                defaults={
                    'type': item['type'],
                    'star_rating': item.get('star_rating'),
                    'address': item['address'],
                    'area': item['area'],
                    'city': item['city'],
                    'latitude': item.get('latitude'),
                    'longitude': item.get('longitude'),
                    'images': item.get('images') or [],
                    'description': item['description'],
                    'amenities': item.get('amenities') or [],
                    'check_in_time': item['check_in_time'],
                    'check_out_time': item['check_out_time'],
                    'minimum_stay': item['minimum_stay'],
                    'license_number': item.get('license_number', ''),
                    'verified': item.get('verified', False),
                    'featured': item.get('featured', False),
                    'cancellation_policy': cancellation,
                    'pricing_rules': pricing_rules,
                    'advance_payment_percent': 30,
                },
            )
            for room_data in item.get('rooms') or []:
                Room.objects.update_or_create(
                    hotel=hotel,
                    room_number=room_data['room_number'],
                    defaults={
                        'type': room_data['type'],
                        'floor': room_data['floor'],
                        'capacity': room_data['capacity'],
                        'base_price': Decimal(room_data['base_price']),
                        'amenities': ['WiFi', 'AC'],
                        'images': [],
                        'description': f'{room_data["type"].title()} room',
                        'available': True,
                    },
                )
            hotel.refresh_room_counts()
            self.stdout.write(f'  {hotel.name} → {hotel.id} ({hotel.total_rooms} rooms)')

        self.stdout.write(self.style.SUCCESS('Seeded hotels complete.'))
