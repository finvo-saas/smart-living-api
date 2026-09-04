"""Seed portfolio, billing, and subscription demo data for Phase 3."""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User, UserProfile
from billing.models import (
    Bill,
    BillItem,
    BillItemType,
    BillStatus,
    BillTemplate,
    BillTemplateItem,
    CalculationType,
    MeterReading,
    MeterType,
    PropertyKind,
)
from billing.services.generation import default_due_date
from portfolio.models import Building, Flat, FlatStatus, Floor, Tenancy, TenancyStatus
from subscriptions.services import ensure_default_plans, get_or_create_owner_subscription


class Command(BaseCommand):
    help = 'Seed owner portfolio with building, flats, tenancy, bill, template, and meter reading.'

    def handle(self, *args, **options):
        ensure_default_plans()

        owner_phone = '+8801712345678'
        owner, created = User.objects.get_or_create(
            phone=owner_phone,
            defaults={
                'name': 'Abdul Karim',
                'role': Role.OWNER,
                'is_phone_verified': True,
                'role_selected': True,
            },
        )
        if not created and owner.role != Role.OWNER:
            owner.role = Role.OWNER
            owner.save(update_fields=['role', 'updated_at'])

        UserProfile.objects.get_or_create(user=owner)
        sub = get_or_create_owner_subscription(owner)
        self.stdout.write(
            self.style.SUCCESS(
                f'Owner {owner.phone} ({owner.id}) subscription={sub.plan.tier}',
            ),
        )

        renter_phone = '+8801710000001'
        renter, _ = User.objects.get_or_create(
            phone=renter_phone,
            defaults={
                'name': 'Rahim Uddin',
                'email': 'rahim.uddin@gmail.com',
                'role': Role.RENTER,
                'is_phone_verified': True,
                'role_selected': True,
            },
        )
        UserProfile.objects.get_or_create(user=renter)

        building, _ = Building.objects.update_or_create(
            owner=owner,
            name='Green Valley',
            defaults={
                'address': 'House 45, Road 7, Block C, Mirpur-10',
                'city': 'Dhaka',
                'total_floors': 2,
                'total_flats': 4,
            },
        )

        floors = {}
        for num in (1, 2):
            floor, _ = Floor.objects.update_or_create(
                building=building,
                floor_number=num,
                defaults={'name': f'Floor {num}'},
            )
            floors[num] = floor

        flat_specs = [
            ('1A', 1, 12000, FlatStatus.OCCUPIED),
            ('1B', 1, 12000, FlatStatus.AVAILABLE),
            ('2A', 2, 15000, FlatStatus.AVAILABLE),
            ('2B', 2, 15000, FlatStatus.AVAILABLE),
        ]
        flats = {}
        for flat_number, floor_num, rent, status in flat_specs:
            flat, _ = Flat.objects.update_or_create(
                building=building,
                flat_number=flat_number,
                defaults={
                    'floor': floors[floor_num],
                    'floor_number': floor_num,
                    'rent': Decimal(str(rent)),
                    'status': status,
                    'area': 850 if floor_num == 1 else 1100,
                    'bedrooms': 2 if floor_num == 1 else 3,
                    'bathrooms': 1 if floor_num == 1 else 2,
                },
            )
            flats[flat_number] = flat

        occupied = flats['1A']
        Tenancy.objects.filter(flat=occupied, status=TenancyStatus.ACTIVE).exclude(
            tenant=renter,
        ).update(
            status=TenancyStatus.ENDED,
            end_date=timezone.localdate(),
        )
        tenancy, _ = Tenancy.objects.update_or_create(
            flat=occupied,
            tenant=renter,
            status=TenancyStatus.ACTIVE,
            defaults={
                'start_date': date(2024, 1, 15),
                'tenant_name': renter.name,
                'tenant_phone': renter.phone,
                'tenant_email': renter.email,
                'tenant_nid': '1234567890123',
                'tenant_address': 'Village: Shyampur, District: Dhaka',
            },
        )

        building.refresh_counts()

        template, _ = BillTemplate.objects.update_or_create(
            owner=owner,
            name='Standard Apartment Bill',
            property_id=building.id,
            defaults={
                'description': 'Monthly rent + utilities',
                'property_type': PropertyKind.APARTMENT,
                'is_active': True,
            },
        )
        BillTemplateItem.objects.filter(template=template).delete()
        BillTemplateItem.objects.create(
            template=template,
            description='Monthly Rent',
            type=BillItemType.RENT,
            calculation_type=CalculationType.FIXED,
            fixed_amount=Decimal('12000'),
        )
        BillTemplateItem.objects.create(
            template=template,
            description='Electricity',
            type=BillItemType.UTILITY,
            calculation_type=CalculationType.METER,
            unit_rate=Decimal('8.5'),
            meter_type=MeterType.ELECTRICITY,
        )

        meter, _ = MeterReading.objects.update_or_create(
            owner=owner,
            property_id=building.id,
            flat=occupied,
            month='March',
            year=2024,
            defaults={
                'property_type': PropertyKind.APARTMENT,
                'electricity': 1250.0,
                'gas': 45.0,
                'water': 30.0,
                'previous_electricity': 1200.0,
                'previous_gas': 40.0,
                'previous_water': 28.0,
                'electricity_consumption': 50.0,
                'gas_consumption': 5.0,
                'water_consumption': 2.0,
                'submitted_by': owner,
            },
        )

        bill, _ = Bill.objects.update_or_create(
            owner=owner,
            property_id=building.id,
            flat=occupied,
            month='March',
            year=2024,
            defaults={
                'tenant': renter,
                'tenant_name': renter.name,
                'tenant_id_snapshot': str(renter.id),
                'property_type': PropertyKind.APARTMENT,
                'property_name': building.name,
                'flat_number': occupied.flat_number,
                'amount': Decimal('12500'),
                'due_date': default_due_date(2024, 'March'),
                'status': BillStatus.UNPAID,
                'template': template,
                'meter_reading': meter,
            },
        )
        BillItem.objects.filter(bill=bill).delete()
        BillItem.objects.create(
            bill=bill,
            description='Monthly Rent',
            amount=Decimal('12000'),
            type=BillItemType.RENT,
        )
        BillItem.objects.create(
            bill=bill,
            description='Utility Bill',
            amount=Decimal('500'),
            type=BillItemType.UTILITY,
        )

        self.stdout.write(self.style.SUCCESS('Seed complete — IDs:'))
        self.stdout.write(f'  owner_id={owner.id}')
        self.stdout.write(f'  renter_id={renter.id}')
        self.stdout.write(f'  building_id={building.id}')
        self.stdout.write(f'  floor_ids={[str(f.id) for f in floors.values()]}')
        self.stdout.write(f'  flat_ids={[str(f.id) for f in flats.values()]}')
        self.stdout.write(f'  tenancy_id={tenancy.id}')
        self.stdout.write(f'  template_id={template.id}')
        self.stdout.write(f'  meter_reading_id={meter.id}')
        self.stdout.write(f'  bill_id={bill.id}')
