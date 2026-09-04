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
    RenterSerializer,
)
from portfolio.services.renter_history import get_renter_history
from subscriptions.services import assert_can_add_flat, get_flat_limit_status


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
        planned_flats = serializer.validated_data.get('total_flats', 0)
        if planned_flats:
            status_data = get_flat_limit_status(request.user)
            if status_data['max'] >= 0 and planned_flats > status_data['max']:
                raise InvalidError(
                    f'Plan allows up to {status_data["max"]} flats.',
                )
        building = serializer.save(owner=request.user)
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
        building = serializer.save()
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
        flat = serializer.save(building=building, floor=floor)
        building.refresh_counts()
        return Response(
            api_success(_serialize_flat(flat)),
            status=status.HTTP_201_CREATED,
        )


class FlatDetailView(APIView):
    permission_classes = [IsAuthenticated]

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

        Tenancy.objects.filter(flat=flat, status=TenancyStatus.ACTIVE).update(
            status=TenancyStatus.ENDED,
            end_date=timezone.localdate(),
        )
        tenancy = Tenancy.objects.create(
            flat=flat,
            tenant=tenant,
            start_date=start,
            status=TenancyStatus.ACTIVE,
            tenant_name=data['name'].strip(),
            tenant_phone=normalize_bd_phone(data['phone']),
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
        today = timezone.localdate()
        updated = Tenancy.objects.filter(
            flat=flat,
            status=TenancyStatus.ACTIVE,
        ).update(status=TenancyStatus.ENDED, end_date=today)
        if not updated:
            raise InvalidError('No active tenancy for this flat.')
        flat.status = FlatStatus.AVAILABLE
        flat.save(update_fields=['status', 'updated_at'])
        flat.building.refresh_counts()
        from listings.services.inventory import sync_flat_listing

        sync_flat_listing(flat)
        return Response(api_success(_serialize_flat(flat)))


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
        return Response(
            api_success(
                {
                    'buildings': BuildingSerializer(buildings, many=True).data,
                    'flats': FlatSerializer(flats, many=True).data,
                    'messList': [],
                },
            ),
        )
