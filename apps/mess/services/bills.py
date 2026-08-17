"""Mess bill get-or-create using billing.Bill."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from billing.models import Bill, BillItem, BillItemType, BillStatus, PropertyKind
from billing.serializers import BillSerializer
from billing.services.generation import MONTH_NAMES, default_due_date
from core.exceptions import InvalidError


def get_or_create_mess_bill(user_or_tenant, data: dict) -> dict:
    """
    Create or return current-month unpaid mess bill.

    data keys: mess, tenantName, seatNumber?, monthlyFee?, studentId?
    user_or_tenant: authenticated User (tenant) or None
    """
    mess = data['mess']
    tenant_name = data.get('tenantName', '').strip()
    if not tenant_name:
        raise InvalidError('tenantName is required.')

    tenant = user_or_tenant if getattr(user_or_tenant, 'is_authenticated', False) else None
    if tenant and not tenant_name:
        tenant_name = tenant.name or f'User {tenant.phone[-4:]}'

    now = timezone.now()
    month = MONTH_NAMES[now.month]
    year = now.year

    qs = Bill.objects.filter(
        property_type=PropertyKind.MESS,
        property_id=mess.id,
        month=month,
        year=year,
        status=BillStatus.UNPAID,
        is_deleted=False,
    )
    if tenant:
        qs = qs.filter(tenant=tenant)
    else:
        qs = qs.filter(tenant_name=tenant_name, tenant__isnull=True)

    existing = qs.select_related('tenant').prefetch_related('items').first()
    if existing:
        return BillSerializer(existing).data

    monthly_fee = data.get('monthlyFee')
    if monthly_fee is None:
        monthly_fee = mess.monthly_fee
    amount = Decimal(str(monthly_fee))

    seat_number = data.get('seatNumber', '') or ''
    student_id = data.get('studentId', '') or ''

    with transaction.atomic():
        bill = Bill.objects.create(
            owner=mess.owner,
            tenant=tenant,
            tenant_name=tenant_name,
            tenant_id_snapshot=student_id,
            property_type=PropertyKind.MESS,
            property_name=mess.name,
            property_id=mess.id,
            seat_number=seat_number,
            month=month,
            year=year,
            amount=amount,
            due_date=default_due_date(year, month, day=5),
            status=BillStatus.UNPAID,
        )
        BillItem.objects.create(
            bill=bill,
            description='Monthly mess fee',
            amount=amount,
            type=BillItemType.RENT,
        )

    bill = Bill.objects.prefetch_related('items').get(pk=bill.pk)
    return BillSerializer(bill).data
