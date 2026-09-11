from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponseRedirect

from billing.models import (
    Bill,
    BillGenerationRule,
    BillItem,
    BillStatus,
    BillTemplate,
    BillTemplateItem,
    MeterReading,
)
from billing.serializers import (
    BillGenerationRuleSerializer,
    BillRuleBulkSerializer,
    BillSerializer,
    BillTemplateBulkSerializer,
    BillTemplateSerializer,
    BulkGenerateBillSerializer,
    GenerateBillSerializer,
    MarkPaidSerializer,
    MeterReadingBulkSerializer,
    MeterReadingSerializer,
)
from billing.services.generation import bulk_generate_bills, create_bill_from_payload
from billing.services.public_pdf import (
    resolve_bill_for_public_pdf,
    storage_url_without_template_tag,
)
from billing.services.whatsapp_share import prepare_whatsapp_share
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from core.services.media import media_storage
from portfolio.models import Building, Flat, Tenancy, TenancyStatus
from portfolio.serializers import BuildingSerializer, FlatSerializer, RenterSerializer
from mess.models import Mess
from mess.serializers import MessSerializer


def _owner_bill(user, bill_id) -> Bill:
    try:
        bill = Bill.objects.prefetch_related('items').select_related(
            'meter_reading',
            'template',
        ).get(pk=bill_id, is_deleted=False)
    except Bill.DoesNotExist as exc:
        raise NotFoundError('Bill not found.') from exc
    if bill.owner_id != user.id and user.role != 'admin':
        if bill.tenant_id != user.id:
            raise ForbiddenError('You cannot access this bill.')
    return bill


def _serialize_bill(bill):
    return BillSerializer(bill).data


def _serialize_bills(qs):
    return BillSerializer(qs, many=True).data


def _board_renters(owner):
    tenancies = (
        Tenancy.objects.filter(
            flat__building__owner=owner,
            status=TenancyStatus.ACTIVE,
        )
        .select_related('tenant')
        .order_by('tenant_id', '-start_date')
    )
    seen = set()
    renters = []
    for tenancy in tenancies:
        if tenancy.tenant_id in seen:
            continue
        seen.add(tenancy.tenant_id)
        renters.append(
            RenterSerializer(
                {
                    'id': tenancy.tenant_id,
                    'name': tenancy.tenant_name or tenancy.tenant.name,
                    'phone': tenancy.tenant_phone or tenancy.tenant.phone,
                    'email': tenancy.tenant_email or tenancy.tenant.email or '',
                    'nid': tenancy.tenant_nid or '',
                    'address': tenancy.tenant_address or '',
                    'joinedDate': tenancy.start_date.isoformat(),
                },
            ).data,
        )
    return renters


class BillsBoardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        owner = request.user
        bills = Bill.objects.filter(owner=owner, is_deleted=False).prefetch_related(
            'items',
        ).select_related('meter_reading', 'template')
        templates = BillTemplate.objects.filter(owner=owner).prefetch_related('items')
        rules = BillGenerationRule.objects.filter(owner=owner).select_related('template')
        readings = MeterReading.objects.filter(owner=owner).select_related('flat')
        buildings = Building.objects.filter(owner=owner)
        flats = Flat.objects.filter(building__owner=owner).prefetch_related('tenancies')
        messes = Mess.objects.filter(owner=owner, is_deleted=False).order_by('-created_at')

        return Response(
            api_success(
                {
                    'bills': _serialize_bills(bills),
                    'templates': BillTemplateSerializer(templates, many=True).data,
                    'rules': BillGenerationRuleSerializer(rules, many=True).data,
                    'meterReadings': MeterReadingSerializer(readings, many=True).data,
                    'buildings': BuildingSerializer(buildings, many=True).data,
                    'flats': FlatSerializer(flats, many=True).data,
                    'renters': _board_renters(owner),
                    'messList': MessSerializer(messes, many=True).data,
                },
            ),
        )


class TenantBillsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bills = Bill.objects.filter(
            tenant=request.user,
            is_deleted=False,
        ).prefetch_related('items').select_related('meter_reading', 'template')
        return Response(api_success(_serialize_bills(bills)))


class OwnerBillsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bills = Bill.objects.filter(
            owner=request.user,
            is_deleted=False,
        ).prefetch_related('items').select_related('meter_reading', 'template')
        return Response(api_success(_serialize_bills(bills)))


class BillDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        bill = _owner_bill(request.user, pk)
        return Response(api_success(_serialize_bill(bill)))

    @transaction.atomic
    def patch(self, request, pk):
        """Owner edits a bill they generated (amount, due date, items, status)."""
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can edit bills.')
        bill = _owner_bill(request.user, pk)
        entry = dict(request.data)
        items_data = entry.pop('items', None)

        if 'tenantName' in entry:
            bill.tenant_name = entry['tenantName']
        if 'flatNumber' in entry:
            bill.flat_number = entry.get('flatNumber') or ''
        if 'seatNumber' in entry:
            bill.seat_number = entry.get('seatNumber') or ''
        if 'month' in entry and entry['month']:
            bill.month = entry['month']
        if 'year' in entry and entry['year']:
            bill.year = entry['year']
        if 'amount' in entry and entry['amount'] is not None:
            bill.amount = entry['amount']
        if entry.get('dueDate'):
            bill.due_date = entry['dueDate']
        if 'paidDate' in entry:
            bill.paid_date = entry.get('paidDate') or None
        if 'status' in entry and entry['status']:
            bill.status = entry['status']
        bill.save()

        if items_data is not None:
            bill.items.all().delete()
            for item in items_data:
                BillItem.objects.create(
                    bill=bill,
                    description=item.get('description') or item.get('name') or 'Item',
                    amount=item['amount'],
                    type=item.get('type', 'other'),
                    calculation_type=item.get('calculationType', ''),
                    unit_rate=item.get('unitRate'),
                    previous_reading=item.get('previousReading'),
                    current_reading=item.get('currentReading'),
                    consumption=item.get('consumption'),
                )
            # Keep header amount aligned with line items when amount omitted.
            if 'amount' not in entry:
                from django.db.models import Sum

                total = bill.items.aggregate(s=Sum('amount'))['s']
                if total is not None:
                    bill.amount = total
                    bill.save(update_fields=['amount', 'updated_at'])

        bill = _owner_bill(request.user, bill.id)
        return Response(api_success(_serialize_bill(bill)))


class BillsBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can bulk-update bills.')

        payload = request.data
        if not isinstance(payload, list):
            raise InvalidError('Expected an array of bills.')

        existing_ids = {
            str(b.id): b
            for b in Bill.objects.filter(owner=request.user, is_deleted=False)
        }
        seen_ids = set()
        results = []

        for raw_entry in payload:
            entry = dict(raw_entry)
            bill_id = entry.get('id')
            items_data = entry.pop('items', [])

            if bill_id and str(bill_id) in existing_ids:
                bill = existing_ids[str(bill_id)]
                seen_ids.add(str(bill_id))
                bill.tenant_name = entry.get('tenantName', bill.tenant_name)
                bill.tenant_id_snapshot = entry.get('tenantId', bill.tenant_id_snapshot)
                bill.property_type = entry.get('propertyType', bill.property_type)
                bill.property_name = entry.get('propertyName', bill.property_name)
                bill.property_id = entry.get('propertyId', bill.property_id)
                bill.flat_number = entry.get('flatNumber', bill.flat_number)
                bill.seat_number = entry.get('seatNumber', bill.seat_number)
                bill.month = entry.get('month', bill.month)
                bill.year = entry.get('year', bill.year)
                bill.amount = entry.get('amount', bill.amount)
                if entry.get('dueDate'):
                    bill.due_date = entry['dueDate']
                if entry.get('paidDate'):
                    bill.paid_date = entry['paidDate']
                bill.status = entry.get('status', bill.status)
                bill.save()

                if items_data is not None:
                    bill.items.all().delete()
                    for item in items_data:
                        BillItem.objects.create(
                            bill=bill,
                            description=item['description'],
                            amount=item['amount'],
                            type=item.get('type', 'other'),
                            calculation_type=item.get('calculationType', ''),
                            unit_rate=item.get('unitRate'),
                            previous_reading=item.get('previousReading'),
                            current_reading=item.get('currentReading'),
                            consumption=item.get('consumption'),
                        )
                results.append(bill)
            else:
                bill = Bill.objects.create(
                    owner=request.user,
                    tenant_name=entry.get('tenantName', 'Tenant'),
                    tenant_id_snapshot=entry.get('tenantId', ''),
                    property_type=entry.get('propertyType', 'apartment'),
                    property_name=entry.get('propertyName', ''),
                    property_id=entry.get('propertyId'),
                    flat_number=entry.get('flatNumber', ''),
                    seat_number=entry.get('seatNumber', ''),
                    month=entry.get('month', 'January'),
                    year=entry.get('year', timezone.localdate().year),
                    amount=entry.get('amount', 0),
                    due_date=entry.get('dueDate') or timezone.localdate(),
                    paid_date=entry.get('paidDate'),
                    status=entry.get('status', BillStatus.UNPAID),
                )
                for item in items_data:
                    BillItem.objects.create(
                        bill=bill,
                        description=item['description'],
                        amount=item['amount'],
                        type=item.get('type', 'other'),
                        calculation_type=item.get('calculationType', ''),
                        unit_rate=item.get('unitRate'),
                        previous_reading=item.get('previousReading'),
                        current_reading=item.get('currentReading'),
                        consumption=item.get('consumption'),
                    )
                results.append(bill)

        stale = set(existing_ids.keys()) - seen_ids
        if stale:
            Bill.objects.filter(id__in=stale, owner=request.user).update(is_deleted=True)

        refreshed = Bill.objects.filter(
            id__in=[b.id for b in results],
        ).prefetch_related('items')
        return Response(api_success(_serialize_bills(refreshed)))


class GenerateBillView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can generate bills.')
        serializer = GenerateBillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bill = create_bill_from_payload(request.user, serializer.validated_data)
        return Response(
            api_success(_serialize_bill(bill)),
            status=status.HTTP_201_CREATED,
        )


class BulkGenerateBillsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can bulk-generate bills.')
        serializer = BulkGenerateBillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bills = bulk_generate_bills(request.user, serializer.validated_data)
        return Response(
            api_success(_serialize_bills(bills)),
            status=status.HTTP_201_CREATED,
        )


class MarkBillPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        bill = _owner_bill(request.user, pk)
        if bill.owner_id != request.user.id and request.user.role != 'admin':
            raise ForbiddenError('Only the bill owner can mark bills paid.')
        serializer = MarkPaidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        paid_at = serializer.validated_data.get('paidAt') or timezone.localdate()
        bill.status = BillStatus.PAID
        bill.paid_date = paid_at
        bill.save(update_fields=['status', 'paid_date', 'updated_at'])
        return Response(api_success(_serialize_bill(bill)))


class BillWhatsAppShareView(APIView):
    """
    Owner-only: generate/upload bill PDF and return a wa.me deep link.

    Opens the owner's WhatsApp (logged-in device) to message the tenant.
    Free — no Business API / credits.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        bill = _owner_bill(request.user, pk)
        if bill.owner_id != request.user.id and request.user.role != 'admin':
            raise ForbiddenError('Only the bill owner can share bills on WhatsApp.')
        regenerate = bool(request.data.get('regeneratePdf')) if isinstance(request.data, dict) else False
        payload = prepare_whatsapp_share(
            bill, regenerate_pdf=regenerate, request=request
        )
        return Response(api_success(payload))


class BillDueRemindView(APIView):
    """
    Owner-only due reminder for a bill.

    channel=whatsapp (default): returns wa.me deep link (no PDF).
    channel=sms: sends SMS via gateway to the tenant phone.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from billing.services.whatsapp_share import (
            prepare_whatsapp_due_reminder,
            send_sms_due_reminder,
        )

        bill = _owner_bill(request.user, pk)
        if bill.owner_id != request.user.id and request.user.role != 'admin':
            raise ForbiddenError('Only the bill owner can send due reminders.')
        if bill.status == BillStatus.PAID:
            raise InvalidError('This bill is already paid.')

        channel = (request.data.get('channel') or 'whatsapp').lower()
        if channel == 'sms':
            payload = send_sms_due_reminder(bill)
        else:
            payload = prepare_whatsapp_due_reminder(bill)
        return Response(api_success(payload))


class BillsBulkDueRemindView(APIView):
    """Prepare WhatsApp due reminders for many unpaid owner bills (apartment-friendly)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from billing.services.whatsapp_share import prepare_whatsapp_due_reminder

        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can bulk-remind bills.')
        bill_ids = request.data.get('billIds') or []
        property_type = request.data.get('propertyType')  # optional filter
        unpaid_only = request.data.get('unpaidOnly', True)

        qs = Bill.objects.filter(owner=request.user, is_deleted=False)
        if bill_ids:
            qs = qs.filter(id__in=bill_ids)
        if property_type:
            qs = qs.filter(property_type=property_type)
        if unpaid_only:
            qs = qs.exclude(status=BillStatus.PAID)

        results = []
        errors = []
        for bill in qs.select_related('tenant')[:100]:
            try:
                results.append(prepare_whatsapp_due_reminder(bill))
            except Exception as exc:  # noqa: BLE001
                errors.append({'billId': str(bill.id), 'error': str(exc)})
        return Response(api_success({'reminders': results, 'errors': errors}))


class PublicBillPdfView(APIView):
    """
    Unauthenticated branded PDF link → redirect to DigitalOcean Spaces.

    Example:
    ``/api/v1/public/bills/green-valley-mess/4caa1b87….pdf``
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, property_slug, file_id):
        bill = resolve_bill_for_public_pdf(property_slug, file_id)
        if not bill or not bill.pdf_key:
            raise NotFoundError('Bill PDF not found.')
        target = storage_url_without_template_tag(bill.pdf_url)
        if not target.startswith('http'):
            target = media_storage.url_for(bill.pdf_key, request=request)
        if not target:
            raise NotFoundError('Bill PDF not available.')
        return HttpResponseRedirect(target)


class BillTemplatesBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can manage bill templates.')
        payload = request.data
        if not isinstance(payload, list):
            raise InvalidError('Expected an array of templates.')

        existing = {
            str(t.id): t
            for t in BillTemplate.objects.filter(owner=request.user).prefetch_related('items')
        }
        seen = set()
        saved = []

        for entry in payload:
            tid = entry.get('id')
            items = entry.get('items', [])
            # Ignore client-generated non-UUID ids (e.g. template173…) so we create fresh rows.
            if tid:
                try:
                    UUID(str(tid))
                except (ValueError, TypeError):
                    tid = None
            if tid and str(tid) in existing:
                tmpl = existing[str(tid)]
                seen.add(str(tid))
                tmpl.name = entry.get('name', tmpl.name)
                tmpl.description = entry.get('description', tmpl.description)
                tmpl.property_id = entry.get('propertyId', tmpl.property_id)
                tmpl.property_type = entry.get('propertyType', tmpl.property_type)
                flat_raw = entry.get('flatId', tmpl.flat_id)
                tmpl.flat_id = flat_raw or None
                tmpl.seat_id = entry.get('seatId') or ''
                tmpl.is_active = entry.get('isActive', tmpl.is_active)
                tmpl.save()
                tmpl.items.all().delete()
            else:
                flat_raw = entry.get('flatId')
                tmpl = BillTemplate.objects.create(
                    owner=request.user,
                    name=entry.get('name', 'Template'),
                    description=entry.get('description', ''),
                    property_id=entry.get('propertyId'),
                    property_type=entry.get('propertyType', 'apartment'),
                    flat_id=flat_raw or None,
                    seat_id=entry.get('seatId') or '',
                    is_active=entry.get('isActive', True),
                )

            for item in items:
                meter = item.get('meterType') or ''
                BillTemplateItem.objects.create(
                    template=tmpl,
                    description=item['description'],
                    type=item.get('type', 'other'),
                    calculation_type=item.get('calculationType', 'fixed'),
                    fixed_amount=item.get('fixedAmount'),
                    unit_rate=item.get('unitRate'),
                    percentage=item.get('percentage'),
                    base_item_id=item.get('baseItemId') or '',
                    meter_type=meter,
                    service_charge=item.get('serviceCharge'),
                )
            saved.append(tmpl)

        stale = set(existing.keys()) - seen
        if stale:
            BillTemplate.objects.filter(id__in=stale, owner=request.user).delete()

        qs = BillTemplate.objects.filter(
            id__in=[t.id for t in saved],
        ).prefetch_related('items')
        return Response(api_success(BillTemplateSerializer(qs, many=True).data))


class ActiveBillTemplatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = BillTemplate.objects.filter(
            owner=request.user,
            is_active=True,
        ).prefetch_related('items')
        return Response(api_success(BillTemplateSerializer(qs, many=True).data))


class BillTemplatesByPropertyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        property_id = request.query_params.get('property_id')
        if not property_id:
            raise InvalidError('property_id query parameter is required.')
        try:
            UUID(property_id)
        except ValueError as exc:
            raise InvalidError('Invalid property_id.') from exc
        qs = BillTemplate.objects.filter(
            owner=request.user,
            property_id=property_id,
        ).prefetch_related('items')
        return Response(api_success(BillTemplateSerializer(qs, many=True).data))


class BillRulesBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can manage bill rules.')
        payload = request.data
        if not isinstance(payload, list):
            raise InvalidError('Expected an array of rules.')

        existing = {
            str(r.id): r
            for r in BillGenerationRule.objects.filter(owner=request.user)
        }
        seen = set()
        saved = []

        for entry in payload:
            rid = entry.get('id')
            # Ignore client-generated non-UUID ids so we create fresh rows.
            if rid:
                try:
                    UUID(str(rid))
                except (TypeError, ValueError):
                    rid = None
            template_id = entry.get('templateId')
            if not template_id:
                raise InvalidError('templateId is required for each rule.')

            property_id = entry.get('propertyId') or None
            property_type = entry.get('propertyType') or ''

            if rid and str(rid) in existing:
                rule = existing[str(rid)]
                seen.add(str(rid))
                rule.name = entry.get('name', rule.name)
                rule.description = entry.get('description') or ''
                rule.property_id = property_id
                rule.property_type = property_type
                rule.template_id = template_id
                rule.schedule = entry.get('schedule', rule.schedule)
                rule.is_active = entry.get('isActive', rule.is_active)
                if entry.get('lastRun'):
                    rule.last_run = entry['lastRun']
                if entry.get('nextRun'):
                    rule.next_run = entry['nextRun']
                rule.save()
            else:
                rule = BillGenerationRule.objects.create(
                    owner=request.user,
                    name=entry.get('name', 'Rule'),
                    description=entry.get('description') or '',
                    property_id=property_id,
                    property_type=property_type,
                    template_id=template_id,
                    schedule=entry.get('schedule') or {},
                    is_active=entry.get('isActive', True),
                    last_run=entry.get('lastRun'),
                    next_run=entry.get('nextRun'),
                )
            saved.append(rule)

        stale = set(existing.keys()) - seen
        if stale:
            BillGenerationRule.objects.filter(id__in=stale, owner=request.user).delete()

        qs = BillGenerationRule.objects.filter(id__in=[r.id for r in saved])
        return Response(api_success(BillGenerationRuleSerializer(qs, many=True).data))


class ActiveBillRulesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = BillGenerationRule.objects.filter(owner=request.user, is_active=True)
        return Response(api_success(BillGenerationRuleSerializer(qs, many=True).data))


class MeterReadingsBulkView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can manage meter readings.')
        payload = request.data
        if not isinstance(payload, list):
            raise InvalidError('Expected an array of meter readings.')

        existing = {
            str(r.id): r for r in MeterReading.objects.filter(owner=request.user)
        }
        seen = set()
        saved = []

        for entry in payload:
            rid = entry.get('id')
            # Ignore client-generated non-UUID ids so we create fresh rows.
            if rid:
                try:
                    UUID(str(rid))
                except (TypeError, ValueError):
                    rid = None
            flat_raw = entry.get('flatId')
            flat_id = flat_raw or None
            seat_id = entry.get('seatId') or ''
            if rid and str(rid) in existing:
                reading = existing[str(rid)]
                seen.add(str(rid))
                reading.property_id = entry.get('propertyId', reading.property_id)
                reading.property_type = entry.get('propertyType', reading.property_type)
                reading.flat_id = flat_id
                reading.seat_id = seat_id
                reading.month = entry.get('month', reading.month)
                reading.year = entry.get('year', reading.year)
                reading.electricity = entry.get('electricity')
                reading.gas = entry.get('gas')
                reading.water = entry.get('water')
                reading.previous_electricity = entry.get('previousElectricity')
                reading.previous_gas = entry.get('previousGas')
                reading.previous_water = entry.get('previousWater')
                reading.electricity_consumption = entry.get('electricityConsumption')
                reading.gas_consumption = entry.get('gasConsumption')
                reading.water_consumption = entry.get('waterConsumption')
                reading.save()
            else:
                reading = MeterReading.objects.create(
                    owner=request.user,
                    property_id=entry['propertyId'],
                    property_type=entry.get('propertyType', 'apartment'),
                    flat_id=flat_id,
                    seat_id=seat_id,
                    month=entry['month'],
                    year=entry['year'],
                    electricity=entry.get('electricity'),
                    gas=entry.get('gas'),
                    water=entry.get('water'),
                    previous_electricity=entry.get('previousElectricity'),
                    previous_gas=entry.get('previousGas'),
                    previous_water=entry.get('previousWater'),
                    electricity_consumption=entry.get('electricityConsumption'),
                    gas_consumption=entry.get('gasConsumption'),
                    water_consumption=entry.get('waterConsumption'),
                    submitted_by=request.user,
                )
            saved.append(reading)

        stale = set(existing.keys()) - seen
        if stale:
            MeterReading.objects.filter(id__in=stale, owner=request.user).delete()

        qs = MeterReading.objects.filter(id__in=[r.id for r in saved])
        return Response(api_success(MeterReadingSerializer(qs, many=True).data))


def _meter_lookup(owner, params, *, previous: bool):
    property_id = params.get('property_id')
    flat_id = params.get('flat_id') or None
    month = params.get('month')
    year = params.get('year')
    if not all([property_id, month, year]):
        raise InvalidError('property_id, month, and year are required.')

    from billing.services.generation import _month_name_to_number, MONTH_NAMES

    target_month = month
    target_year = int(year)
    if previous:
        month_num = _month_name_to_number(month)
        if not month_num:
            return None
        target_month = MONTH_NAMES[month_num - 1 if month_num > 1 else 12]
        target_year = int(year) if month_num > 1 else int(year) - 1

    qs = MeterReading.objects.filter(
        owner=owner,
        property_id=property_id,
        month=target_month,
        year=target_year,
    )
    if flat_id:
        qs = qs.filter(flat_id=flat_id)
    else:
        qs = qs.filter(flat__isnull=True)

    return qs.order_by('-submitted_at').first()


class PreviousMeterReadingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reading = _meter_lookup(request.user, request.query_params, previous=True)
        if not reading:
            return Response(api_success(None))
        return Response(api_success(MeterReadingSerializer(reading).data))


class CurrentMeterReadingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reading = _meter_lookup(request.user, request.query_params, previous=False)
        if not reading:
            return Response(api_success(None))
        return Response(api_success(MeterReadingSerializer(reading).data))
