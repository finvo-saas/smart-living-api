from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role, User
from accounts.phone import normalize_bd_phone
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from portfolio.models import Building, Flat, FlatStatus, Floor, Tenancy, TenancyStatus
from portfolio.serializers import (
    AssignRenterSerializer,
    BuildingPatchSerializer,
    BuildingSerializer,
    BuildingWriteSerializer,
    FlatPatchSerializer,
    FlatSerializer,
    FlatWriteSerializer,
    FloorPatchSerializer,
    FloorSerializer,
    FloorStatsSerializer,
    FloorWriteSerializer,
    MyTenancySerializer,
    RenterSerializer,
    VacateFlatSerializer,
)
from portfolio.services.layout import sync_building_layout
from portfolio.services.renter_history import get_renter_history
from subscriptions.services import assert_can_add_flat
from mess.models import Mess
from mess.serializers import MessSerializer


def _require_owner(user):
    if user.role not in (Role.OWNER, Role.ADMIN):
        raise ForbiddenError('Only owners can manage portfolio.')


def _owner_building(user, building_id) -> Building:
    try:
        building = Building.objects.get(pk=building_id)
    except Building.DoesNotExist as exc:
        raise NotFoundError('Building not found.') from exc
    if building.owner_id != user.id and user.role != Role.ADMIN:
        raise ForbiddenError('You can only access your own buildings.')
    return building


def _owner_flat(user, flat_id) -> Flat:
    try:
        flat = Flat.objects.select_related('building').get(pk=flat_id)
    except Flat.DoesNotExist as exc:
        raise NotFoundError('Flat not found.') from exc
    if flat.building.owner_id != user.id and user.role != Role.ADMIN:
        raise ForbiddenError('You can only access your own flats.')
    return flat


def _owner_floor(user, floor_id) -> Floor:
    try:
        floor = Floor.objects.select_related('building').prefetch_related('flats').get(
            pk=floor_id,
        )
    except Floor.DoesNotExist as exc:
        raise NotFoundError('Floor not found.') from exc
    if floor.building.owner_id != user.id and user.role != Role.ADMIN:
        raise ForbiddenError('You can only access your own floors.')
    return floor


def _serialize_building(building):
    return BuildingSerializer(building).data


def _serialize_flat(flat):
    return FlatSerializer(flat).data


def _serialize_floor(floor):
    return FloorSerializer(floor).data


def _floor_stats(floor: Floor) -> dict:
    flats = list(floor.flats.all())
    total = len(flats)
    occupied = sum(1 for f in flats if f.status == FlatStatus.OCCUPIED)
    available = sum(1 for f in flats if f.status == FlatStatus.AVAILABLE)
    maintenance = sum(1 for f in flats if f.status == FlatStatus.MAINTENANCE)
    total_rent = sum(float(f.rent) for f in flats)
    collected = sum(float(f.rent) for f in flats if f.status == FlatStatus.OCCUPIED)
    pending = total_rent - collected
    occupancy = round((occupied / total) * 100, 2) if total else 0.0
    return FloorStatsSerializer(
        {
            'floorId': floor.id,
            'floorNumber': floor.floor_number,
            'totalFlats': total,
            'occupiedFlats': occupied,
            'availableFlats': available,
            'maintenanceFlats': maintenance,
            'totalRent': total_rent,
            'collectedRent': collected,
            'pendingRent': pending,
            'occupancyRate': occupancy,
        },
    ).data


def _get_or_create_renter(phone: str, name: str, email: str = '') -> User:
    normalized = normalize_bd_phone(phone)
    user, created = User.objects.get_or_create(
        phone=normalized,
        defaults={
            'name': name.strip(),
            'email': email or '',
            'role': Role.RENTER,
            'is_phone_verified': True,
            'role_selected': True,
        },
    )
    if not created:
        updates = []
        if name.strip() and not user.name:
            user.name = name.strip()
            updates.append('name')
        if email and not user.email:
            user.email = email
            updates.append('email')
        if updates:
            user.save(update_fields=updates + ['updated_at'])
    return user


class BuildingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Building.objects.filter(owner=request.user).order_by('-created_at')
        return Response(api_success(BuildingSerializer(qs, many=True).data))

    def post(self, request):
        _require_owner(request.user)
        serializer = BuildingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        layouts = serializer.validated_data.pop('floorLayouts', None)
        building = serializer.save(owner=request.user)
        if layouts:
            building = sync_building_layout(
                building,
                [
                    {
                        'floor_number': item['floorNumber'],
                        'flat_count': item['flatCount'],
                    }
                    for item in layouts
                ],
            )
        else:
            building.refresh_counts()
        return Response(
            api_success(_serialize_building(building)),
            status=status.HTTP_201_CREATED,
        )


class BuildingAllListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Building.objects.all().order_by('-created_at')
        return Response(api_success(BuildingSerializer(qs, many=True).data))


class BuildingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        building = _owner_building(request.user, pk)
        return Response(api_success(_serialize_building(building)))

    def patch(self, request, pk):
        building = _owner_building(request.user, pk)
        serializer = BuildingPatchSerializer(building, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        layouts = serializer.validated_data.pop('floorLayouts', None)
        building = serializer.save()
        if layouts:
            building = sync_building_layout(
                building,
                [
                    {
                        'floor_number': item['floorNumber'],
                        'flat_count': item['flatCount'],
                    }
                    for item in layouts
                ],
            )
        else:
            building.refresh_counts()
        return Response(api_success(_serialize_building(building)))


class BuildingFloorListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, building_id):
        building = _owner_building(request.user, building_id)
        floors = (
            Floor.objects.filter(building=building)
            .prefetch_related('flats')
            .order_by('floor_number')
        )
        return Response(api_success(FloorSerializer(floors, many=True).data))

    def post(self, request, building_id):
        _require_owner(request.user)
        building = _owner_building(request.user, building_id)
        serializer = FloorWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        floor_number = serializer.validated_data['floor_number']
        if Floor.objects.filter(building=building, floor_number=floor_number).exists():
            raise InvalidError(f'Floor {floor_number} already exists in this building.')
        floor = serializer.save(building=building)
        building.refresh_counts()
        return Response(
            api_success(_serialize_floor(floor)),
            status=status.HTTP_201_CREATED,
        )


class FloorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        floor = _owner_floor(request.user, pk)
        return Response(api_success(_serialize_floor(floor)))

    def patch(self, request, pk):
        floor = _owner_floor(request.user, pk)
        serializer = FloorPatchSerializer(floor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_number = serializer.validated_data.get('floor_number')
        if new_number and new_number != floor.floor_number:
            if Floor.objects.filter(
                building=floor.building,
                floor_number=new_number,
            ).exclude(pk=floor.pk).exists():
                raise InvalidError(f'Floor {new_number} already exists.')
        floor = serializer.save()
        floor.building.refresh_counts()
        return Response(api_success(_serialize_floor(floor)))

    def delete(self, request, pk):
        floor = _owner_floor(request.user, pk)
        building = floor.building
        if floor.flats.exists():
            raise InvalidError('Remove or reassign flats before deleting this floor.')
        floor.delete()
        building.refresh_counts()
        return Response(api_success(None))


class FloorStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        floor = _owner_floor(request.user, pk)
        return Response(api_success(_floor_stats(floor)))


class BuildingFlatListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, building_id):
        building = _owner_building(request.user, building_id)
        flats = Flat.objects.filter(building=building).prefetch_related('tenancies')
        return Response(api_success(FlatSerializer(flats, many=True).data))


class FlatListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        flats = (
            Flat.objects.filter(building__owner=request.user)
            .select_related('building')
            .prefetch_related('tenancies')
            .order_by('building__name', 'floor_number', 'flat_number')
        )
        return Response(api_success(FlatSerializer(flats, many=True).data))

    def post(self, request):
        _require_owner(request.user)
        assert_can_add_flat(request.user)
        serializer = FlatWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        building_id = serializer.validated_data.pop('building_id', None)
        if not building_id:
            raise InvalidError('buildingId is required.')
        building = _owner_building(request.user, building_id)
        floor_number = serializer.validated_data.get('floor_number', 1)
        floor = Floor.objects.filter(
            building=building,
            floor_number=floor_number,
        ).first()
        if floor is None:
            floor = Floor.objects.create(
                building=building,
                floor_number=floor_number,
                name=f'Floor {floor_number}',
            )
        if Flat.objects.filter(
            building=building,
            flat_number=serializer.validated_data['flat_number'],
        ).exists():
            raise InvalidError('A flat with this number already exists in the building.')
        flat = serializer.save(building=building, floor=floor)
        building.refresh_counts()
        return Response(
            api_success(_serialize_flat(flat)),
            status=status.HTTP_201_CREATED,
        )


class FlatDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        flat = _owner_flat(request.user, pk)
        return Response(api_success(_serialize_flat(flat)))

    def patch(self, request, pk):
        flat = _owner_flat(request.user, pk)
        serializer = FlatPatchSerializer(flat, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        floor_number = serializer.validated_data.get('floor_number')
        if floor_number is not None:
            floor = Floor.objects.filter(
                building=flat.building,
                floor_number=floor_number,
            ).first()
            flat.floor = floor
        flat = serializer.save()
        flat.building.refresh_counts()
        return Response(api_success(_serialize_flat(flat)))

    def delete(self, request, pk):
        flat = _owner_flat(request.user, pk)
        if flat.status == FlatStatus.OCCUPIED:
            raise InvalidError('Vacate the flat before deleting it.')
        if Tenancy.objects.filter(flat=flat, status=TenancyStatus.ACTIVE).exists():
            raise InvalidError('Vacate the flat before deleting it.')
        building = flat.building
        flat.delete()
        building.refresh_counts()
        return Response(api_success(None))


class FlatEnsureListingView(APIView):
    """Create/link a public apartment listing for a vacant (or any) flat."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        _require_owner(request.user)
        flat = _owner_flat(request.user, pk)
        publish = request.data.get('publish', True)
        if isinstance(publish, str):
            publish = publish.lower() not in ('0', 'false', 'no')
        from listings.services.inventory import ensure_listing_for_flat
        from listings.serializers import PropertySerializer

        listing = ensure_listing_for_flat(flat, publish=bool(publish))
        flat.refresh_from_db()
        return Response(
            api_success(
                {
                    'listingId': str(listing.id),
                    'bookUrl': f'/listings/{listing.id}',
                    'flat': _serialize_flat(flat),
                    'listing': PropertySerializer(
                        listing,
                        context={'request': request},
                    ).data,
                },
            ),
        )


class FlatUpdateTenancyView(APIView):
    """PATCH active tenancy details on an occupied flat (owner-created assign)."""

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, pk):
        _require_owner(request.user)
        flat = _owner_flat(request.user, pk)
        tenancy = (
            Tenancy.objects.filter(flat=flat, status=TenancyStatus.ACTIVE)
            .select_related('tenant')
            .first()
        )
        if not tenancy:
            raise InvalidError('No active tenancy for this flat.')

        serializer = AssignRenterSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updates = []
        if 'name' in data:
            tenancy.tenant_name = data['name'].strip()
            updates.append('tenant_name')
        if 'phone' in data:
            tenancy.tenant_phone = normalize_bd_phone(data['phone'])
            updates.append('tenant_phone')
        if 'whatsapp' in data:
            tenancy.tenant_whatsapp = data.get('whatsapp') or ''
            updates.append('tenant_whatsapp')
        if 'email' in data:
            tenancy.tenant_email = data.get('email') or ''
            updates.append('tenant_email')
        if 'nid' in data:
            tenancy.tenant_nid = data.get('nid') or ''
            updates.append('tenant_nid')
        if 'address' in data:
            tenancy.tenant_address = data.get('address') or ''
            updates.append('tenant_address')
        if 'deposit' in data:
            tenancy.deposit = data.get('deposit')
            updates.append('deposit')
        if 'notes' in data:
            tenancy.notes = (data.get('notes') or '').strip()
            updates.append('notes')
        if 'joinedDate' in data and data.get('joinedDate'):
            tenancy.start_date = data['joinedDate']
            updates.append('start_date')

        if updates:
            tenancy.save(update_fields=[*updates, 'updated_at'])

        # Keep linked user profile snapshots in sync when phone/name change.
        tenant = tenancy.tenant
        user_updates = []
        if 'name' in data and data['name'].strip() and not tenant.name:
            tenant.name = data['name'].strip()
            user_updates.append('name')
        if 'whatsapp' in data and data.get('whatsapp'):
            tenant.whatsapp_number = data['whatsapp']
            user_updates.append('whatsapp_number')
        if user_updates:
            tenant.save(update_fields=[*user_updates, 'updated_at'])

        return Response(api_success(_serialize_flat(flat)))


class FlatAssignRenterView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        _require_owner(request.user)
        flat = _owner_flat(request.user, pk)
        if flat.status == FlatStatus.OCCUPIED:
            raise InvalidError('Flat is already occupied. Vacate first.')

        serializer = AssignRenterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tenant = _get_or_create_renter(
            data['phone'],
            data['name'],
            data.get('email', ''),
        )
        start = data.get('joinedDate') or timezone.localdate()
        deposit = data.get('deposit')
        notes = (data.get('notes') or '').strip()

        Tenancy.objects.filter(flat=flat, status=TenancyStatus.ACTIVE).update(
            status=TenancyStatus.ENDED,
            end_date=timezone.localdate(),
        )
        tenancy = Tenancy.objects.create(
            flat=flat,
            tenant=tenant,
            start_date=start,
            status=TenancyStatus.ACTIVE,
            deposit=deposit,
            notes=notes,
            tenant_name=data['name'].strip(),
            tenant_phone=normalize_bd_phone(data['phone']),
            tenant_whatsapp=data.get('whatsapp') or tenant.whatsapp_number,
            tenant_email=data.get('email', '') or '',
            tenant_nid=data.get('nid', '') or '',
            tenant_address=data.get('address', '') or '',
        )
        flat.status = FlatStatus.OCCUPIED
        flat.save(update_fields=['status', 'updated_at'])
        flat.building.refresh_counts()
        from listings.services.inventory import sync_flat_listing

        sync_flat_listing(flat)

        renter = {
            'id': str(tenant.id),
            'name': tenancy.tenant_name,
            'phone': tenancy.tenant_phone,
            'whatsapp': tenancy.tenant_whatsapp or '',
            'email': tenancy.tenant_email or None,
            'nid': tenancy.tenant_nid or None,
            'address': tenancy.tenant_address or None,
            'joinedDate': tenancy.start_date.isoformat(),
        }
        return Response(
            api_success({'flat': _serialize_flat(flat), 'renter': renter}),
            status=status.HTTP_201_CREATED,
        )


class FlatVacateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        _require_owner(request.user)
        flat = _owner_flat(request.user, pk)
        serializer = VacateFlatSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        today = timezone.localdate()
        tenancy = (
            Tenancy.objects.filter(flat=flat, status=TenancyStatus.ACTIVE)
            .order_by('-start_date')
            .first()
        )
        if not tenancy:
            raise InvalidError('No active tenancy for this flat.')

        note_parts = []
        if tenancy.notes:
            note_parts.append(tenancy.notes.strip())
        advance_note = (data.get('advanceNote') or '').strip()
        if advance_note:
            note_parts.append(f'Vacate ({today.isoformat()}): {advance_note}')
        deposit_returned = data.get('depositReturned')
        if deposit_returned is not None:
            note_parts.append(
                f'Deposit returned: {deposit_returned} on {today.isoformat()}',
            )

        tenancy.status = TenancyStatus.ENDED
        tenancy.end_date = today
        tenancy.notes = '\n'.join(part for part in note_parts if part)
        tenancy.save(update_fields=['status', 'end_date', 'notes', 'updated_at'])

        flat.status = FlatStatus.AVAILABLE
        flat.save(update_fields=['status', 'updated_at'])
        flat.building.refresh_counts()
        from listings.services.inventory import sync_flat_listing

        sync_flat_listing(flat)
        from bookings.models import BookingStatus, PropertyBooking

        PropertyBooking.objects.filter(
            flat=flat,
            status=BookingStatus.APPROVED,
            is_deleted=False,
        ).update(status=BookingStatus.COMPLETED, completed_at=timezone.now())
        return Response(api_success(_serialize_flat(flat)))


def _serialize_my_tenancy(tenancy: Tenancy) -> dict:
    flat = tenancy.flat
    building = flat.building
    owner = building.owner
    owner_whatsapp = getattr(owner, 'whatsapp_number', '') or ''
    return MyTenancySerializer(
        {
            'id': tenancy.id,
            'status': tenancy.status,
            'startDate': tenancy.start_date.isoformat(),
            'endDate': tenancy.end_date.isoformat() if tenancy.end_date else None,
            'deposit': float(tenancy.deposit) if tenancy.deposit is not None else None,
            'notes': tenancy.notes or '',
            'flat': {
                'id': str(flat.id),
                'flatNumber': flat.flat_number,
                'floor': flat.floor_number,
                'rent': float(flat.rent),
                'status': flat.status,
                'area': flat.area,
                'bedrooms': flat.bedrooms,
                'bathrooms': flat.bathrooms,
                'buildingId': str(building.id),
            },
            'building': {
                'id': str(building.id),
                'name': building.name,
                'address': building.address,
                'city': building.city,
            },
            'owner': {
                'id': str(owner.id),
                'name': owner.name or '',
                'phone': owner.phone or '',
                'whatsapp': owner_whatsapp,
            },
        },
    ).data


class MyTenanciesView(APIView):
    """GET /tenancies/mine/ — active (and optional past) tenancies for the logged-in renter."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = (request.query_params.get('status') or 'active').lower()
        qs = (
            Tenancy.objects.filter(tenant=request.user)
            .select_related(
                'flat',
                'flat__building',
                'flat__building__owner',
            )
            .order_by('-start_date')
        )
        if status_filter == 'active':
            qs = qs.filter(status=TenancyStatus.ACTIVE)
        elif status_filter == 'ended':
            qs = qs.filter(status=TenancyStatus.ENDED)
        elif status_filter not in ('all', ''):
            raise InvalidError('status must be active, ended, or all.')

        payload = [_serialize_my_tenancy(t) for t in qs]
        return Response(api_success(payload))


class RenterListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenancies = (
            Tenancy.objects.filter(
                flat__building__owner=request.user,
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
                        'whatsapp': (
                            tenancy.tenant_whatsapp
                            or tenancy.tenant.whatsapp_number
                            or ''
                        ),
                        'email': tenancy.tenant_email or tenancy.tenant.email or '',
                        'nid': tenancy.tenant_nid or '',
                        'address': tenancy.tenant_address or '',
                        'joinedDate': tenancy.start_date.isoformat(),
                    },
                ).data,
            )
        return Response(api_success(renters))


class RenterHistoryView(APIView):
    """GET /renters/{id}/history/ — tenancies, bills, complaints for a renter."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payload = get_renter_history(viewer=request.user, renter_id=pk)
        return Response(api_success(payload))


class PortfolioSnapshotView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        buildings = Building.objects.filter(owner=request.user).order_by('-created_at')
        flats = (
            Flat.objects.filter(building__owner=request.user)
            .select_related('building')
            .prefetch_related('tenancies')
        )
        messes = Mess.objects.filter(
            owner=request.user,
            is_deleted=False,
        ).order_by('-created_at')
        return Response(
            api_success(
                {
                    'buildings': BuildingSerializer(buildings, many=True).data,
                    'flats': FlatSerializer(flats, many=True).data,
                    'messList': MessSerializer(messes, many=True).data,
                },
            ),
        )
