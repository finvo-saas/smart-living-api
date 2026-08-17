from decimal import Decimal

from rest_framework import serializers

from portfolio.models import Building, Flat, FlatStatus, Floor, Tenancy, TenancyStatus


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _date_str(dt) -> str:
    if dt is None:
        return ''
    return dt.date().isoformat() if hasattr(dt, 'date') else str(dt)


class RenterSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField(required=False, allow_blank=True)
    nid = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    joinedDate = serializers.CharField()


def _active_tenancy(flat: Flat):
    return (
        flat.tenancies.filter(status=TenancyStatus.ACTIVE)
        .select_related('tenant')
        .order_by('-start_date')
        .first()
    )


def _renter_from_tenancy(tenancy: Tenancy | None) -> dict | None:
    if not tenancy:
        return None
    tenant = tenancy.tenant
    return {
        'id': str(tenant.id),
        'name': tenancy.tenant_name or tenant.name or f'User {tenant.phone[-4:]}',
        'phone': tenancy.tenant_phone or tenant.phone,
        'email': tenancy.tenant_email or tenant.email or None,
        'nid': tenancy.tenant_nid or None,
        'address': tenancy.tenant_address or None,
        'joinedDate': tenancy.start_date.isoformat(),
    }


class FlatSerializer(serializers.ModelSerializer):
    flatNumber = serializers.CharField(source='flat_number')
    floor = serializers.IntegerField(source='floor_number')
    rent = serializers.SerializerMethodField()
    buildingId = serializers.UUIDField(source='building_id', read_only=True)
    renter = serializers.SerializerMethodField()

    class Meta:
        model = Flat
        fields = (
            'id',
            'flatNumber',
            'floor',
            'rent',
            'status',
            'buildingId',
            'renter',
            'area',
            'bedrooms',
            'bathrooms',
        )

    def get_rent(self, obj):
        return _money(obj.rent)

    def get_renter(self, obj):
        tenancy = _active_tenancy(obj)
        return _renter_from_tenancy(tenancy)


class FlatWriteSerializer(serializers.ModelSerializer):
    flatNumber = serializers.CharField(source='flat_number')
    floor = serializers.IntegerField(source='floor_number', required=False, default=1)
    buildingId = serializers.UUIDField(source='building_id', required=False)
    rent = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = Flat
        fields = (
            'flatNumber',
            'floor',
            'rent',
            'status',
            'buildingId',
            'area',
            'bedrooms',
            'bathrooms',
        )

    def validate_rent(self, value):
        if value is None or Decimal(value) < 0:
            raise serializers.ValidationError('Rent must be zero or positive.')
        return value


class FlatPatchSerializer(serializers.ModelSerializer):
    flatNumber = serializers.CharField(source='flat_number', required=False)
    floor = serializers.IntegerField(source='floor_number', required=False)
    rent = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
    )

    class Meta:
        model = Flat
        fields = (
            'flatNumber',
            'floor',
            'rent',
            'status',
            'area',
            'bedrooms',
            'bathrooms',
        )


class BuildingSerializer(serializers.ModelSerializer):
    ownerId = serializers.UUIDField(source='owner_id', read_only=True)
    totalFloors = serializers.IntegerField(source='total_floors')
    totalFlats = serializers.IntegerField(source='total_flats', read_only=True)
    occupiedFlats = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = Building
        fields = (
            'id',
            'ownerId',
            'name',
            'address',
            'city',
            'totalFloors',
            'totalFlats',
            'occupiedFlats',
            'createdAt',
        )

    def get_occupiedFlats(self, obj):
        return obj.occupied_flats

    def get_createdAt(self, obj):
        return _date_str(obj.created_at)


class BuildingWriteSerializer(serializers.ModelSerializer):
    totalFloors = serializers.IntegerField(source='total_floors', required=False, default=1)
    totalFlats = serializers.IntegerField(source='total_flats', required=False, default=0)

    class Meta:
        model = Building
        fields = ('name', 'address', 'city', 'totalFloors', 'totalFlats')

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Building name is required.')
        return value.strip()


class BuildingPatchSerializer(serializers.ModelSerializer):
    totalFloors = serializers.IntegerField(source='total_floors', required=False)
    totalFlats = serializers.IntegerField(source='total_flats', required=False)

    class Meta:
        model = Building
        fields = ('name', 'address', 'city', 'totalFloors', 'totalFlats')


class FloorSerializer(serializers.ModelSerializer):
    buildingId = serializers.UUIDField(source='building_id', read_only=True)
    floorNumber = serializers.IntegerField(source='floor_number')
    totalFlats = serializers.SerializerMethodField()
    occupiedFlats = serializers.SerializerMethodField()
    availableFlats = serializers.SerializerMethodField()
    maintenanceFlats = serializers.SerializerMethodField()
    flats = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()
    updatedAt = serializers.SerializerMethodField()

    class Meta:
        model = Floor
        fields = (
            'id',
            'buildingId',
            'floorNumber',
            'name',
            'totalFlats',
            'occupiedFlats',
            'availableFlats',
            'maintenanceFlats',
            'flats',
            'notes',
            'createdAt',
            'updatedAt',
        )

    def _floor_flats(self, obj):
        if hasattr(obj, '_prefetched_flats'):
            return obj._prefetched_flats
        return list(obj.flats.all())

    def get_totalFlats(self, obj):
        return len(self._floor_flats(obj))

    def get_occupiedFlats(self, obj):
        return sum(1 for f in self._floor_flats(obj) if f.status == FlatStatus.OCCUPIED)

    def get_availableFlats(self, obj):
        return sum(1 for f in self._floor_flats(obj) if f.status == FlatStatus.AVAILABLE)

    def get_maintenanceFlats(self, obj):
        return sum(
            1 for f in self._floor_flats(obj) if f.status == FlatStatus.MAINTENANCE
        )

    def get_flats(self, obj):
        return FlatSerializer(self._floor_flats(obj), many=True).data

    def get_createdAt(self, obj):
        return _date_str(obj.created_at)

    def get_updatedAt(self, obj):
        return _date_str(obj.updated_at)


class FloorWriteSerializer(serializers.ModelSerializer):
    floorNumber = serializers.IntegerField(source='floor_number')

    class Meta:
        model = Floor
        fields = ('floorNumber', 'name', 'notes')


class FloorPatchSerializer(serializers.ModelSerializer):
    floorNumber = serializers.IntegerField(source='floor_number', required=False)

    class Meta:
        model = Floor
        fields = ('floorNumber', 'name', 'notes')


class AssignRenterSerializer(serializers.Serializer):
    name = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True)
    nid = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    joinedDate = serializers.DateField(required=False)


class FloorStatsSerializer(serializers.Serializer):
    floorId = serializers.UUIDField()
    floorNumber = serializers.IntegerField()
    totalFlats = serializers.IntegerField()
    occupiedFlats = serializers.IntegerField()
    availableFlats = serializers.IntegerField()
    maintenanceFlats = serializers.IntegerField()
    totalRent = serializers.FloatField()
    collectedRent = serializers.FloatField()
    pendingRent = serializers.FloatField()
    occupancyRate = serializers.FloatField()
