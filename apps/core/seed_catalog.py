"""Shared Bangladesh seed identities and extra catalog rows.

Keep demo phones stable so existing docs and OTP logins still work:
  Admins   +8801711111111 / 1722222222 / 1733333333
  Owner    +8801712345678  Abdul Karim
  Renter   +8801710000001  Rahim Uddin
"""

from accounts.models import Role, User, UserProfile

# Unsplash listing/hotel photos (public CDN — no local media required).
IMG = {
    'room': 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800',
    'apt': 'https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800',
    'apt2': 'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800',
    'kitchen': 'https://images.unsplash.com/photo-1556912172-45b7abe8b7c8?w=800',
    'hostel': 'https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=800',
    'living': 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800',
    'hotel': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800',
    'hotel2': 'https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=800',
    'guest': 'https://images.unsplash.com/photo-1590490360182-c33d57733427?w=800',
    'beach': 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=800',
    'resort': 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=800',
}


OWNERS = [
    {
        'phone': '+8801712345678',
        'name': 'Abdul Karim',
        'email': 'abdul.karim@smartliving.bd',
        'locale': 'bn',
    },
    {
        'phone': '+8801712345679',
        'name': 'Fatima Begum',
        'email': 'fatima.begum@smartliving.bd',
        'locale': 'bn',
    },
    {
        'phone': '+8801712345681',
        'name': 'Shahidul Islam',
        'email': 'shahidul.islam@smartliving.bd',
        'locale': 'bn',
    },
    {
        'phone': '+8801812345678',
        'name': 'Nusrat Jahan',
        'email': 'nusrat.jahan@smartliving.bd',
        'locale': 'bn',
    },
    {
        'phone': '+8801912345678',
        'name': 'Rafiq Ahmed',
        'email': 'rafiq.ahmed@smartliving.bd',
        'locale': 'bn',
    },
    {
        'phone': '+8801612345678',
        'name': 'Mahmuda Akter',
        'email': 'mahmuda.akter@smartliving.bd',
        'locale': 'bn',
    },
    {
        'phone': '+8801512345678',
        'name': 'Tanvir Hasan',
        'email': 'tanvir.hasan@smartliving.bd',
        'locale': 'en',
    },
]

# Listing owner Karim Hossain is an owner, not a mess student.
OWNERS.append(
    {
        'phone': '+8801712345680',
        'name': 'Karim Hossain',
        'email': 'karim.hossain@smartliving.bd',
        'locale': 'bn',
    },
)

RENTERS = [
    {
        'phone': '+8801710000001',
        'name': 'Rahim Uddin',
        'email': 'rahim.uddin@gmail.com',
        'locale': 'bn',
        'job_info': {
            'occupation': 'Undergraduate student',
            'institution': 'University of Dhaka',
            'workplace': 'Dhaka',
        },
    },
    {
        'phone': '+8801710000002',
        'name': 'Sadia Rahman',
        'email': 'sadia.rahman@gmail.com',
        'locale': 'bn',
        'job_info': {
            'occupation': 'Software engineer',
            'company': 'bKash Limited',
            'workplace': 'Dhaka',
        },
    },
    {
        'phone': '+8801710000003',
        'name': 'Imran Hossain',
        'email': 'imran.hossain@gmail.com',
        'locale': 'bn',
        'job_info': {
            'occupation': 'Bank officer',
            'company': 'Dutch-Bangla Bank',
            'workplace': 'Motijheel',
        },
    },
    {
        'phone': '+8801710000004',
        'name': 'Nafisa Chowdhury',
        'email': 'nafisa.chowdhury@gmail.com',
        'locale': 'en',
        'job_info': {
            'occupation': 'Lecturer',
            'institution': 'BRAC University',
            'workplace': 'Merul Badda',
        },
    },
    {
        'phone': '+8801710000005',
        'name': 'Arif Khan',
        'email': 'arif.khan@gmail.com',
        'locale': 'bn',
        'job_info': {
            'occupation': 'Graphic designer',
            'company': 'Freelance',
            'workplace': 'Chattogram',
        },
    },
    {
        'phone': '+8801710000006',
        'name': 'Farzana Islam',
        'email': 'farzana.islam@gmail.com',
        'locale': 'bn',
        'job_info': {
            'occupation': 'Nurse',
            'company': 'Square Hospital',
            'workplace': 'Panthapath',
        },
    },
    {
        'phone': '+8801710000007',
        'name': 'Mehedi Hasan',
        'email': 'mehedi.hasan@gmail.com',
        'locale': 'bn',
        'job_info': {
            'occupation': 'CUET student',
            'institution': 'Chittagong University of Engineering & Technology',
            'workplace': 'Chattogram',
        },
    },
    {
        'phone': '+8801710000008',
        'name': 'Tania Akter',
        'email': 'tania.akter@gmail.com',
        'locale': 'bn',
        'job_info': {
            'occupation': 'SUST student',
            'institution': 'Shahjalal University of Science and Technology',
            'workplace': 'Sylhet',
        },
    },
]


def ensure_user(*, phone: str, name: str, role: str, email: str = '', locale: str = 'en', **extra) -> User:
    defaults = {
        'name': name,
        'email': email,
        'role': role,
        'role_selected': True,
        'is_phone_verified': True,
        'locale': locale,
        'is_active': True,
    }
    user, created = User.objects.get_or_create(phone=phone, defaults=defaults)
    updates = []
    if not created:
        if not user.name:
            user.name = name
            updates.append('name')
        if email and not user.email:
            user.email = email
            updates.append('email')
        if user.role != role and role != Role.ADMIN:
            # Never demote platform admins.
            if not getattr(user, 'admin_profile', None):
                user.role = role
                user.role_selected = True
                updates.extend(['role', 'role_selected'])
        if not user.is_phone_verified:
            user.is_phone_verified = True
            updates.append('is_phone_verified')
        if updates:
            user.save(update_fields=[*updates, 'updated_at'])
    profile, _ = UserProfile.objects.get_or_create(user=user)
    job_info = extra.get('job_info')
    if job_info and not profile.job_info:
        profile.job_info = job_info
        profile.emergency_contacts = extra.get(
            'emergency_contacts',
            [{'name': 'Family', 'phone': '+8801711990000', 'relation': 'Parent'}],
        )
        profile.save(update_fields=['job_info', 'emergency_contacts', 'updated_at'])
    return user


EXTRA_LISTINGS = [
    {
        'name': 'Banani Studio Flat',
        'type': 'apartment',
        'rent': 18000,
        'area': 'Banani',
        'address': 'House 12, Road 11, Block F',
        'city': 'Dhaka',
        'latitude': 23.7940,
        'longitude': 90.4043,
        'images': [IMG['apt'], IMG['apt2']],
        'facilities': ['WiFi', 'AC', 'Lift', 'Security', 'Generator'],
        'nearby_facilities': ['Banani Lake', 'Kemal Ataturk Avenue', 'Grocery'],
        'building_age': 4,
        'floor_level': 6,
        'furnishing': 'furnished',
        'parking': True,
        'security': True,
        'verified': True,
        'featured': True,
        'deposit_months': 2,
        'instant_book': True,
        'description': (
            'Furnished studio near Kemal Ataturk Avenue. Ideal for young professionals '
            'working in Gulshan–Banani.'
        ),
        'owner_phone': '+8801712345679',
        'owner_name': 'Fatima Begum',
    },
    {
        'name': 'Mohammadpur Family Mess',
        'type': 'mess',
        'rent': 4000,
        'area': 'Mohammadpur',
        'address': 'Shyamoli Ring Road, House 8',
        'city': 'Dhaka',
        'latitude': 23.7658,
        'longitude': 90.3584,
        'gender': 'male',
        'seat_type': 'shared',
        'meal_included': True,
        'meal_plan': 'all',
        'meal_cost': 2200,
        'images': [IMG['room'], IMG['kitchen']],
        'facilities': ['WiFi', 'Generator', 'Security', 'Common Kitchen', 'CCTV'],
        'nearby_facilities': ['Shyamoli Square', 'Bus Stand', 'City College'],
        'building_age': 7,
        'floor_level': 3,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': True,
        'description': (
            'Home-style meals three times a day. Popular with city college and '
            'office-going bachelors in Mohammadpur.'
        ),
        'owner_phone': '+8801712345678',
        'owner_name': 'Abdul Karim',
    },
    {
        'name': 'Bashundhara R/A 3BHK',
        'type': 'apartment',
        'rent': 28000,
        'area': 'Bashundhara R/A',
        'address': 'Block C, Road 5, House 19',
        'city': 'Dhaka',
        'latitude': 23.8151,
        'longitude': 90.4285,
        'images': [IMG['apt2'], IMG['living']],
        'facilities': ['WiFi', 'AC', 'Lift', 'Parking', 'Security', 'Generator', 'Community'],
        'nearby_facilities': ['Jamuna Future Park', 'NSU', 'IUB'],
        'building_age': 3,
        'floor_level': 8,
        'furnishing': 'semi-furnished',
        'parking': True,
        'security': True,
        'verified': True,
        'deposit_months': 2,
        'description': (
            'South-facing 3 bedroom flat in Bashundhara. Close to universities and '
            'Jamuna Future Park.'
        ),
        'owner_phone': '+8801712345681',
        'owner_name': 'Shahidul Islam',
    },
    {
        'name': 'Ladies Hostel Farmgate',
        'type': 'hostel',
        'rent': 5500,
        'area': 'Farmgate',
        'address': 'Green Road, Khamarbari',
        'city': 'Dhaka',
        'latitude': 23.7563,
        'longitude': 90.3900,
        'gender': 'female',
        'seat_type': 'shared',
        'meal_included': True,
        'meal_plan': 'all',
        'meal_cost': 2000,
        'images': [IMG['hostel'], IMG['room']],
        'facilities': ['WiFi', 'Security', 'CCTV', 'Laundry', 'Generator'],
        'nearby_facilities': ['Farmgate Bus', 'SAARC Fountain', 'Hospitals'],
        'building_age': 6,
        'floor_level': 4,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': True,
        'description': (
            'Secure ladies hostel on Green Road. Meals included, 10 pm gate for safety, '
            'walking distance to Farmgate.'
        ),
        'owner_phone': '+8801812345678',
        'owner_name': 'Nusrat Jahan',
    },
    {
        'name': 'GEC Circle Shared Seat',
        'type': 'mess',
        'rent': 3800,
        'area': 'GEC',
        'address': 'CDA Avenue, GEC Circle',
        'city': 'Chittagong',
        'latitude': 22.3594,
        'longitude': 91.8215,
        'gender': 'male',
        'seat_type': 'shared',
        'meal_included': True,
        'meal_plan': 'all',
        'meal_cost': 1800,
        'images': [IMG['kitchen'], IMG['room']],
        'facilities': ['WiFi', 'Generator', 'Security'],
        'nearby_facilities': ['GEC Circle', 'CUET bus', '2 No Gate'],
        'building_age': 9,
        'floor_level': 2,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': True,
        'description': (
            'Bachelor mess near GEC Circle. Easy commute to CUET, Agrabad offices, and '
            'Chittagong University buses.'
        ),
        'owner_phone': '+8801512345678',
        'owner_name': 'Tanvir Hasan',
    },
    {
        'name': 'Khulshi Hill Apartment',
        'type': 'apartment',
        'rent': 16000,
        'area': 'Khulshi',
        'address': 'Road 2, Khulshi Hills',
        'city': 'Chittagong',
        'latitude': 22.3667,
        'longitude': 91.8060,
        'images': [IMG['apt'], IMG['living']],
        'facilities': ['WiFi', 'Parking', 'Security', 'Generator', 'Balcony'],
        'nearby_facilities': ['CMCH', 'GEC', 'Port Connecting Road'],
        'building_age': 5,
        'floor_level': 3,
        'furnishing': 'semi-furnished',
        'parking': True,
        'security': True,
        'verified': True,
        'deposit_months': 2,
        'description': (
            'Breezy Khulshi apartment with hill view balcony. Suitable for a small family '
            'or two working professionals.'
        ),
        'owner_phone': '+8801512345678',
        'owner_name': 'Tanvir Hasan',
    },
    {
        'name': 'Amberkhana Student Mess',
        'type': 'mess',
        'rent': 3000,
        'area': 'Amberkhana',
        'address': 'Airport Road, Amberkhana',
        'city': 'Sylhet',
        'latitude': 24.9090,
        'longitude': 91.8520,
        'gender': 'male',
        'seat_type': 'shared',
        'meal_included': True,
        'meal_plan': 'lunch',
        'meal_cost': 1400,
        'images': [IMG['room']],
        'facilities': ['WiFi', 'Security', 'Common Kitchen'],
        'nearby_facilities': ['SUST', 'Osmani Airport', 'Bondor Bazar'],
        'building_age': 12,
        'floor_level': 2,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': False,
        'description': (
            'Budget mess for SUST students. Lunch included, kitchen open for dinner. '
            'Quiet after 11 pm.'
        ),
        'owner_phone': '+8801912345678',
        'owner_name': 'Rafiq Ahmed',
    },
    {
        'name': 'Sonadanga Family Flat',
        'type': 'apartment',
        'rent': 11000,
        'area': 'Sonadanga',
        'address': 'Mujgunni, Sonadanga R/A',
        'city': 'Khulna',
        'latitude': 22.8456,
        'longitude': 89.5403,
        'images': [IMG['living'], IMG['apt2']],
        'facilities': ['Parking', 'Security', 'Balcony'],
        'nearby_facilities': ['Khalishpur', 'New Market', 'Khulna University'],
        'building_age': 8,
        'floor_level': 2,
        'furnishing': 'unfurnished',
        'parking': True,
        'security': True,
        'verified': True,
        'deposit_months': 2,
        'description': (
            'Unfurnished 2 bedroom flat in Sonadanga. Close to Khulna University and '
            'city new market.'
        ),
        'owner_phone': '+8801612345678',
        'owner_name': 'Mahmuda Akter',
    },
    {
        'name': 'Rajshahi Shaheb Bazar Hostel',
        'type': 'hostel',
        'rent': 2800,
        'area': 'Shaheb Bazar',
        'address': 'Greater Road, Shaheb Bazar',
        'city': 'Rajshahi',
        'latitude': 24.3745,
        'longitude': 88.6042,
        'gender': 'male',
        'seat_type': 'shared',
        'meal_included': True,
        'meal_plan': 'all',
        'meal_cost': 1500,
        'images': [IMG['hostel']],
        'facilities': ['WiFi', 'Generator', 'Security'],
        'nearby_facilities': ['Rajshahi University', 'Shaheb Bazar', 'Padma River'],
        'building_age': 11,
        'floor_level': 3,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': True,
        'description': (
            'Student hostel near Shaheb Bazar. Three meals, study tables, and generator '
            'during load shedding.'
        ),
        'owner_phone': '+8801612345678',
        'owner_name': 'Mahmuda Akter',
    },
    {
        'name': 'Kolatoli Beach Guest Rooms',
        'type': 'hotel',
        'rent': 2500,
        'area': 'Kolatoli',
        'address': 'Kolatoli Beach Road',
        'city': "Cox's Bazar",
        'latitude': 21.4272,
        'longitude': 92.0058,
        'images': [IMG['beach'], IMG['hotel2']],
        'facilities': ['WiFi', 'AC', 'Parking', 'Sea View'],
        'nearby_facilities': ['Kolatoli Beach', 'Laboni Beach', 'Bazar'],
        'building_age': 4,
        'floor_level': 2,
        'furnishing': 'furnished',
        'parking': True,
        'security': True,
        'verified': True,
        'featured': True,
        'instant_book': True,
        'description': (
            'Nightly rooms two minutes from Kolatoli beach. Good for weekend trips from '
            'Dhaka and Chattogram.'
        ),
        'owner_phone': '+8801512345678',
        'owner_name': 'Tanvir Hasan',
    },
    {
        'name': 'Motijheel Executive Suite',
        'type': 'apartment',
        'rent': 22000,
        'area': 'Motijheel',
        'address': 'Dilkusha C/A, Inner Circular Road',
        'city': 'Dhaka',
        'latitude': 23.7293,
        'longitude': 90.4169,
        'images': [IMG['apt'], IMG['apt2']],
        'facilities': ['WiFi', 'AC', 'Lift', 'Security', 'Generator', 'Parking'],
        'nearby_facilities': ['Bangladesh Bank', 'Motijheel Metro', 'Gulistan'],
        'building_age': 10,
        'floor_level': 9,
        'furnishing': 'furnished',
        'parking': True,
        'security': True,
        'verified': True,
        'deposit_months': 2,
        'description': (
            'Serviced executive suite for bankers and consultants working in Motijheel. '
            'Metro station within walking distance.'
        ),
        'owner_phone': '+8801712345681',
        'owner_name': 'Shahidul Islam',
    },
    {
        'name': 'Rangpur Medical Mess',
        'type': 'mess',
        'rent': 2700,
        'area': 'Medical More',
        'address': 'Rangpur Medical College Road',
        'city': 'Rangpur',
        'latitude': 25.7439,
        'longitude': 89.2752,
        'gender': 'mixed',
        'seat_type': 'single',
        'meal_included': True,
        'meal_plan': 'all',
        'meal_cost': 1600,
        'images': [IMG['room'], IMG['kitchen']],
        'facilities': ['WiFi', 'Security', 'Generator'],
        'nearby_facilities': ['Rangpur Medical College', 'City Mall', 'Terminal'],
        'building_age': 6,
        'floor_level': 2,
        'furnishing': 'furnished',
        'parking': False,
        'security': True,
        'verified': True,
        'description': (
            'Single-seat mess beside Rangpur Medical College. Separate floors for male '
            'and female students.'
        ),
        'owner_phone': '+8801612345678',
        'owner_name': 'Mahmuda Akter',
    },
]


EXTRA_HOTELS = [
    {
        'owner_phone': '+8801512345678',
        'name': 'Long Beach Hotel Cox\'s Bazar',
        'type': 'resort',
        'star_rating': 5,
        'address': '14 Kalatoli Road',
        'area': 'Kolatoli',
        'city': "Cox's Bazar",
        'latitude': 21.4272,
        'longitude': 92.0058,
        'images': [IMG['beach'], IMG['resort'], IMG['hotel2']],
        'description': (
            'Sea-facing resort on Kolatoli beach. Family rooms, rooftop restaurant, and '
            'easy access to Inani and Himchari.'
        ),
        'amenities': [
            'WiFi', 'AC', 'Parking', 'Restaurant', 'Swimming Pool', 'Spa',
            'Sea View', 'Room Service',
        ],
        'check_in_time': '14:00',
        'check_out_time': '11:00',
        'minimum_stay': 1,
        'license_number': 'CXB-HTL-2019-088',
        'verified': True,
        'featured': True,
        'rooms': [
            {'room_number': 'S101', 'type': 'double', 'floor': 1, 'capacity': 2, 'base_price': 8500},
            {'room_number': 'S201', 'type': 'family', 'floor': 2, 'capacity': 4, 'base_price': 12500},
            {'room_number': 'S301', 'type': 'suite', 'floor': 3, 'capacity': 3, 'base_price': 16000},
        ],
    },
    {
        'owner_phone': '+8801912345678',
        'name': 'Rose View Hotel Sylhet',
        'type': 'hotel',
        'star_rating': 4,
        'address': 'Shahjalal Uposhohor',
        'area': 'Uposhohor',
        'city': 'Sylhet',
        'latitude': 24.8949,
        'longitude': 91.8687,
        'images': [IMG['hotel'], IMG['hotel2']],
        'description': (
            'Business hotel in Uposhohor with tea-garden day trips. Close to Osmani '
            'International Airport.'
        ),
        'amenities': ['WiFi', 'AC', 'Parking', 'Restaurant', 'Gym', 'Conference'],
        'check_in_time': '14:00',
        'check_out_time': '12:00',
        'minimum_stay': 1,
        'license_number': 'SYL-HTL-2021-014',
        'verified': True,
        'featured': True,
        'rooms': [
            {'room_number': '401', 'type': 'double', 'floor': 4, 'capacity': 2, 'base_price': 6200},
            {'room_number': '501', 'type': 'suite', 'floor': 5, 'capacity': 3, 'base_price': 9800},
        ],
    },
    {
        'owner_phone': '+8801512345678',
        'name': 'Well Park Residence Chittagong',
        'type': 'hotel',
        'star_rating': 4,
        'address': 'Road 2, Khulshi',
        'area': 'Khulshi',
        'city': 'Chittagong',
        'latitude': 22.3667,
        'longitude': 91.8060,
        'images': [IMG['hotel2'], IMG['guest']],
        'description': (
            'Hill-city hotel for port and garment buyers. Quiet Khulshi location with '
            'airport transfer.'
        ),
        'amenities': ['WiFi', 'AC', 'Parking', 'Restaurant', 'Gym', 'Laundry'],
        'check_in_time': '13:00',
        'check_out_time': '12:00',
        'minimum_stay': 1,
        'license_number': 'CTG-HTL-2018-033',
        'verified': True,
        'featured': False,
        'rooms': [
            {'room_number': '110', 'type': 'single', 'floor': 1, 'capacity': 1, 'base_price': 4200},
            {'room_number': '210', 'type': 'double', 'floor': 2, 'capacity': 2, 'base_price': 5800},
            {'room_number': '310', 'type': 'suite', 'floor': 3, 'capacity': 3, 'base_price': 8900},
        ],
    },
    {
        'owner_phone': '+8801712345678',
        'name': 'Hotel 71 Motijheel',
        'type': 'hotel',
        'star_rating': 3,
        'address': 'Dilkusha C/A',
        'area': 'Motijheel',
        'city': 'Dhaka',
        'latitude': 23.7293,
        'longitude': 90.4169,
        'images': [IMG['guest'], IMG['hotel']],
        'description': (
            'Practical overnight stay for Motijheel meetings. Walking distance to '
            'Bangladesh Bank and the metro.'
        ),
        'amenities': ['WiFi', 'AC', 'Restaurant', 'Laundry'],
        'check_in_time': '14:00',
        'check_out_time': '12:00',
        'minimum_stay': 1,
        'license_number': 'DHA-HTL-2016-071',
        'verified': True,
        'featured': False,
        'rooms': [
            {'room_number': '701', 'type': 'single', 'floor': 7, 'capacity': 1, 'base_price': 3800},
            {'room_number': '702', 'type': 'double', 'floor': 7, 'capacity': 2, 'base_price': 4800},
        ],
    },
]
