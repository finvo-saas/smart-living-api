"""Bill creation from templates, meter readings, and manual payloads."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.models import (
    Bill,
    BillItem,
    BillItemType,
    BillStatus,
    BillTemplate,
    CalculationType,
    MeterReading,
    MeterType,
    PropertyKind,
)
from core.exceptions import InvalidError, NotFoundError
from portfolio.models import Building, Flat, Tenancy, TenancyStatus


MONTH_NAMES = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December',
}


def _month_name_to_number(name: str) -> int | None:
    normalized = name.strip().lower()
    for num, label in MONTH_NAMES.items():
        if label.lower() == normalized:
            return num
    return None


def default_due_date(year: int, month_name: str, day: int = 5) -> date:
    month_num = _month_name_to_number(month_name)
    if not month_num:
        raise InvalidError(f'Invalid month name: {month_name}')
    last_day = monthrange(year, month_num)[1]
    return date(year, month_num, min(day, last_day))


def _meter_value(reading: MeterReading | None, meter_type: str) -> float | None:
    if not reading:
        return None
    mapping = {
        MeterType.ELECTRICITY: reading.electricity,
        MeterType.GAS: reading.gas,
        MeterType.WATER: reading.water,
    }
    return mapping.get(meter_type)


def _previous_meter_value(reading: MeterReading | None, meter_type: str) -> float | None:
    if not reading:
        return None
    mapping = {
        MeterType.ELECTRICITY: reading.previous_electricity,
        MeterType.GAS: reading.previous_gas,
        MeterType.WATER: reading.previous_water,
    }
    return mapping.get(meter_type)


def _calculate_template_item_amount(
    template_item,
    *,
    flat_rent: Decimal,
    meter_reading: MeterReading | None,
    item_amounts: dict[str, Decimal],
) -> tuple[Decimal, dict]:
    calc = template_item.calculation_type
    extras = {}

    if calc == CalculationType.FIXED:
        amount = template_item.fixed_amount or Decimal('0')
    elif calc == CalculationType.METER:
        current = _meter_value(meter_reading, template_item.meter_type)
        previous = _previous_meter_value(meter_reading, template_item.meter_type)
        if current is None:
            amount = Decimal('0')
        else:
            prev = previous or 0
            consumption = max(0, float(current) - float(prev))
            rate = template_item.unit_rate or Decimal('0')
            amount = Decimal(str(consumption)) * rate
            extras = {
                'previous_reading': prev,
                'current_reading': float(current),
                'consumption': consumption,
                'unit_rate': float(rate),
            }
        if template_item.service_charge:
            amount += template_item.service_charge
    elif calc == CalculationType.PERCENTAGE:
        base_id = template_item.base_item_id
        base = item_amounts.get(base_id, flat_rent)
        pct = template_item.percentage or 0
        amount = Decimal(str(base)) * Decimal(str(pct)) / Decimal('100')
    else:
        amount = template_item.fixed_amount or Decimal('0')

    return amount.quantize(Decimal('0.01')), extras


def _active_tenancy(flat: Flat):
    return (
        flat.tenancies.filter(status=TenancyStatus.ACTIVE)
        .select_related('tenant')
        .order_by('-start_date')
        .first()
    )


@transaction.atomic
def create_bill_from_payload(owner, data: dict) -> Bill:
    from accounts.models import User

    property_id = data['propertyId']
    tenant_id = data['tenantId']
    month = data['month']
    year = data['year']
    items_data = data.get('items', [])

    tenant = None
    tenant_name = 'Tenant'
    try:
        tenant = User.objects.get(pk=tenant_id)
        tenant_name = tenant.name or tenant.phone
    except (User.DoesNotExist, ValueError):
        tenant_name = tenant_id

    building = None
    flat = None
    property_name = ''
    flat_number = ''
    try:
        building = Building.objects.get(pk=property_id, owner=owner)
        property_name = building.name
    except Building.DoesNotExist:
        property_name = str(property_id)

    flat_id = data.get('flatId')
    if flat_id:
        try:
            flat = Flat.objects.get(pk=flat_id, building__owner=owner)
            flat_number = flat.flat_number
            if not property_name:
                property_name = flat.building.name
        except Flat.DoesNotExist:
            flat = None

    amount = sum(Decimal(str(i['amount'])) for i in items_data)
    due = default_due_date(year, month)

    template = None
    template_id = data.get('templateId')
    if template_id:
        template = BillTemplate.objects.filter(pk=template_id, owner=owner).first()

    bill = Bill.objects.create(
        owner=owner,
        tenant=tenant,
        tenant_name=tenant_name,
        tenant_id_snapshot=str(tenant_id),
        property_type=data.get('propertyType', PropertyKind.APARTMENT),
        property_name=property_name,
        property_id=property_id,
        flat=flat,
        flat_number=flat_number,
        month=month,
        year=year,
        amount=amount,
        due_date=due,
        status=BillStatus.UNPAID,
        template=template,
    )

    for item in items_data:
        BillItem.objects.create(
            bill=bill,
            description=item['description'],
            amount=item['amount'],
            type=item.get('type', BillItemType.OTHER),
            calculation_type=item.get('calculationType', ''),
            unit_rate=item.get('unitRate'),
            previous_reading=item.get('previousReading'),
            current_reading=item.get('currentReading'),
            consumption=item.get('consumption'),
        )

    return bill


@transaction.atomic
def generate_bill_for_flat(
    owner,
    *,
    building: Building,
    flat: Flat,
    month: str,
    year: int,
    template: BillTemplate | None = None,
    meter_reading: MeterReading | None = None,
    include_unpaid: bool = False,
    due_day: int = 5,
    occupied_only: bool = False,
) -> Bill | None:
    if Bill.objects.filter(
        owner=owner,
        property_id=building.id,
        flat=flat,
        month=month,
        year=year,
        is_deleted=False,
    ).exists():
        if not include_unpaid:
            return None

    tenancy = _active_tenancy(flat)
    if occupied_only and not tenancy:
        return None

    tenant = tenancy.tenant if tenancy else None
    tenant_name = (
        (tenancy.tenant_name or tenant.name or tenant.phone)
        if tenancy and tenant
        else f'Vacant {flat.flat_number}'
    )
    tenant_snapshot = str(tenant.id) if tenant else ''

    item_amounts: dict[str, Decimal] = {}
    line_items: list[dict] = []
    total = Decimal('0')

    if template:
        for tmpl_item in template.items.all():
            amount, extras = _calculate_template_item_amount(
                tmpl_item,
                flat_rent=flat.rent,
                meter_reading=meter_reading,
                item_amounts=item_amounts,
            )
            item_amounts[str(tmpl_item.id)] = amount
            total += amount
            line_items.append(
                {
                    'description': tmpl_item.description,
                    'amount': amount,
                    'type': tmpl_item.type,
                    'calculation_type': tmpl_item.calculation_type,
                    **extras,
                },
            )
    else:
        total = flat.rent
        line_items.append(
            {
                'description': 'Monthly Rent',
                'amount': flat.rent,
                'type': BillItemType.RENT,
                'calculation_type': CalculationType.FIXED,
            },
        )

    due = default_due_date(year, month, day=due_day)
    bill = Bill.objects.create(
        owner=owner,
        tenant=tenant,
        tenant_name=tenant_name,
        tenant_id_snapshot=tenant_snapshot,
        property_type=PropertyKind.APARTMENT,
        property_name=building.name,
        property_id=building.id,
        flat=flat,
        flat_number=flat.flat_number,
        month=month,
        year=year,
        amount=total,
        due_date=due,
        status=BillStatus.UNPAID,
        template=template,
        meter_reading=meter_reading,
    )

    for item in line_items:
        BillItem.objects.create(
            bill=bill,
            description=item['description'],
            amount=item['amount'],
            type=item['type'],
            calculation_type=item.get('calculation_type', ''),
            unit_rate=item.get('unit_rate'),
            previous_reading=item.get('previous_reading'),
            current_reading=item.get('current_reading'),
            consumption=item.get('consumption'),
        )

    return bill


@transaction.atomic
def generate_bill_for_mess_member(
    owner,
    *,
    mess,
    student,
    month: str,
    year: int,
    template: BillTemplate | None = None,
    meter_reading: MeterReading | None = None,
    due_day: int = 5,
) -> Bill | None:
    """Create one mess seat/member bill for a month if it does not already exist."""
    existing = Bill.objects.filter(
        owner=owner,
        property_type=PropertyKind.MESS,
        property_id=mess.id,
        month=month,
        year=year,
        is_deleted=False,
    )
    if student.user_id:
        existing = existing.filter(tenant_id=student.user_id)
    else:
        existing = existing.filter(
            tenant_name=student.name,
            seat_number=student.seat_number or '',
        )
    if existing.exists():
        return None

    base_rent = student.monthly_fee or mess.monthly_fee or Decimal('0')
    item_amounts: dict[str, Decimal] = {}
    line_items: list[dict] = []
    total = Decimal('0')

    if template:
        for tmpl_item in template.items.all():
            amount, extras = _calculate_template_item_amount(
                tmpl_item,
                flat_rent=base_rent,
                meter_reading=meter_reading,
                item_amounts=item_amounts,
            )
            item_amounts[str(tmpl_item.id)] = amount
            total += amount
            line_items.append(
                {
                    'description': tmpl_item.description,
                    'amount': amount,
                    'type': tmpl_item.type,
                    'calculation_type': tmpl_item.calculation_type,
                    **extras,
                },
            )
    else:
        total = base_rent
        line_items.append(
            {
                'description': 'Monthly mess fee',
                'amount': base_rent,
                'type': BillItemType.RENT,
                'calculation_type': CalculationType.FIXED,
            },
        )

    due = default_due_date(year, month, day=due_day)
    bill = Bill.objects.create(
        owner=owner,
        tenant=student.user if student.user_id else None,
        tenant_name=student.name,
        tenant_id_snapshot=str(student.id),
        property_type=PropertyKind.MESS,
        property_name=mess.name,
        property_id=mess.id,
        seat_number=student.seat_number or '',
        month=month,
        year=year,
        amount=total,
        due_date=due,
        status=BillStatus.UNPAID,
        template=template,
        meter_reading=meter_reading,
    )

    for item in line_items:
        BillItem.objects.create(
            bill=bill,
            description=item['description'],
            amount=item['amount'],
            type=item['type'],
            calculation_type=item.get('calculation_type', ''),
            unit_rate=item.get('unit_rate'),
            previous_reading=item.get('previous_reading'),
            current_reading=item.get('current_reading'),
            consumption=item.get('consumption'),
        )

    return bill


@transaction.atomic
def bulk_generate_bills(owner, data: dict) -> list[Bill]:
    building_id = data['buildingId']
    try:
        building = Building.objects.get(pk=building_id, owner=owner)
    except Building.DoesNotExist as exc:
        raise NotFoundError('Building not found.') from exc

    month = data['month']
    year = data['year']
    flat_ids = data.get('flatIds') or []
    template_id = data.get('templateId')
    include_unpaid = data.get('includeUnpaid', False)

    template = None
    if template_id:
        try:
            template = BillTemplate.objects.prefetch_related('items').get(
                pk=template_id,
                owner=owner,
            )
        except BillTemplate.DoesNotExist as exc:
            raise NotFoundError('Bill template not found.') from exc

    flats_qs = Flat.objects.filter(building=building)
    if flat_ids:
        flats_qs = flats_qs.filter(id__in=flat_ids)

    created: list[Bill] = []
    for flat in flats_qs.select_related('building').prefetch_related('tenancies'):
        meter_reading = MeterReading.objects.filter(
            owner=owner,
            property_id=building.id,
            flat=flat,
            month=month,
            year=year,
        ).first()
        bill = generate_bill_for_flat(
            owner,
            building=building,
            flat=flat,
            month=month,
            year=year,
            template=template,
            meter_reading=meter_reading,
            include_unpaid=include_unpaid,
        )
        if bill:
            created.append(bill)

    return created
