from decimal import Decimal

from rest_framework import serializers

from accounts.fields import WhatsAppNumberField
from portfolio.models import Building, Flat, FlatStatus, Floor, Tenancy, TenancyStatus


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _bill(value):
    if value is None:
        return None
    return _money(value)


def _date_str(dt) -> str:
    if dt is None:
        return ''
    return dt.date().isoformat() if hasattr(dt, 'date') else str(dt)


class RenterSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField()
    phone = serializers.CharField()
    whatsapp = serializers.CharField(required=False, allow_blank=True)
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
    from core.services.media import media_storage

    photo_url = ''
    if tenant and getattr(tenant, 'profile_photo', None) and tenant.profile_photo:
        try:
            photo_url = media_storage.absolute_url(tenant.profile_photo.url)
        except Exception:  # noqa: BLE001
            photo_url = ''
    return {
        'id': str(tenant.id),
        'name': tenancy.tenant_name or tenant.name or f'User {tenant.phone[-4:]}',
        'phone': tenancy.tenant_phone or tenant.phone,
        'whatsapp': tenancy.tenant_whatsapp or tenant.whatsapp_number or '',
        'email': tenancy.tenant_email or tenant.email or None,
        'nid': tenancy.tenant_nid or None,
        'address': tenancy.tenant_address or None,
        'joinedDate': tenancy.start_date.isoformat(),
        'photoUrl': photo_url or None,
        'profilePhotoUrl': photo_url or None,
    }


class FlatSerializer(serializers.ModelSerializer):
    flatNumber = serializers.CharField(source='flat_number')
    floor = serializers.IntegerField(source='floor_number')
    rent = serializers.SerializerMethodField()
    buildingId = serializers.UUIDField(source='building_id', read_only=True)
    listingId = serializers.UUIDField(source='listing_id', read_only=True, allow_null=True)
    renter = serializers.SerializerMethodField()
    deposit = serializers.SerializerMethodField()
    tenancyId = serializers.SerializerMethodField()
    electricityBill = serializers.SerializerMethodField()
    gasBill = serializers.SerializerMethodField()
    internetBill = serializers.SerializerMethodField()
    waterBill = serializers.SerializerMethodField()

    class Meta:
        model = Flat
        fields = (
            'id',
            'flatNumber',
            'floor',
            'rent',
            'status',
            'buildingId',
            'listingId',
            'renter',
            'area',
            'bedrooms',
            'bathrooms',
            'deposit',
            'tenancyId',
            'electricityBill',
            'gasBill',
            'internetBill',
            'waterBill',
        )

    def _tenancy(self, obj: Flat):
        if hasattr(obj, '_cached_active_tenancy'):
            return obj._cached_active_tenancy
        tenancy = _active_tenancy(obj)
        obj._cached_active_tenancy = tenancy
        return tenancy

    def get_rent(self, obj):
        return _money(obj.rent)

    def get_renter(self, obj):
        return _renter_from_tenancy(self._tenancy(obj))

    def get_deposit(self, obj):
        tenancy = self._tenancy(obj)
        if not tenancy or tenancy.deposit is None:
            return None
        return _money(tenancy.deposit)

    def get_tenancyId(self, obj):
        tenancy = self._tenancy(obj)
        return str(tenancy.id) if tenancy else None

    def get_electricityBill(self, obj):
        return _bill(obj.electricity_bill)

    def get_gasBill(self, obj):
        return _bill(obj.gas_bill)

    def get_internetBill(self, obj):
        return _bill(obj.internet_bill)

    def get_waterBill(self, obj):
        return _bill(obj.water_bill)


class FlatWriteSerializer(serializers.ModelSerializer):
    flatNumber = serializers.CharField(source='flat_number')
    floor = serializers.IntegerField(source='floor_number', required=False, default=1)
    buildingId = serializers.UUIDField(source='building_id', required=False)
    listingId = serializers.UUIDField(required=False, allow_null=True)
    rent = serializers.DecimalField(max_digits=12, decimal_places=2)
    electricityBill = serializers.DecimalField(
        source='electricity_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    gasBill = serializers.DecimalField(
        source='gas_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    internetBill = serializers.DecimalField(
        source='internet_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    waterBill = serializers.DecimalField(
        source='water_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )

    class Meta:
        model = Flat
        fields = (
            'flatNumber',
            'floor',
            'rent',
            'status',
            'buildingId',
            'listingId',
            'area',
            'bedrooms',
            'bathrooms',
            'electricityBill',
            'gasBill',
            'internetBill',
            'waterBill',
        )

    def validate_rent(self, value):
        if value is None or Decimal(value) < 0:
            raise serializers.ValidationError('Rent must be zero or positive.')
        return value

    def create(self, validated_data):
        listing_id = validated_data.pop('listingId', None)
        flat = super().create(validated_data)
        if listing_id is not None:
            from listings.services.inventory import attach_listing_to_flat

            attach_listing_to_flat(flat, listing_id)
            flat.refresh_from_db()
        from listings.services.inventory import push_flat_bills_to_listing

        push_flat_bills_to_listing(flat)
        return flat


class FlatPatchSerializer(serializers.ModelSerializer):
    flatNumber = serializers.CharField(source='flat_number', required=False)
    floor = serializers.IntegerField(source='floor_number', required=False)
    listingId = serializers.UUIDField(required=False, allow_null=True)
    rent = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
    )
    electricityBill = serializers.DecimalField(
        source='electricity_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    gasBill = serializers.DecimalField(
        source='gas_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    internetBill = serializers.DecimalField(
        source='internet_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    waterBill = serializers.DecimalField(
        source='water_bill', max_digits=12, decimal_places=2, required=False, allow_null=True,
    )

    class Meta:
        model = Flat
        fields = (
            'flatNumber',
            'floor',
            'rent',
            'status',
            'listingId',
            'area',
            'bedrooms',
            'bathrooms',
            'electricityBill',
            'gasBill',
            'internetBill',
            'waterBill',
        )

    def update(self, instance, validated_data):
        listing_id = validated_data.pop('listingId', serializers.empty)
        flat = super().update(instance, validated_data)
        if listing_id is not serializers.empty:
            from listings.services.inventory import attach_listing_to_flat

            attach_listing_to_flat(flat, listing_id)
            flat.refresh_from_db()
        from listings.services.inventory import push_flat_bills_to_listing

        push_flat_bills_to_listing(flat)
        return flat


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
    name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    whatsapp = WhatsAppNumberField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    nid = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    joinedDate = serializers.DateField(required=False)
    deposit = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        # Create/assign still requires name + phone when not partial update of existing.
        if not self.partial:
            if not attrs.get('name'):
                raise serializers.ValidationError({'name': 'Name is required.'})
            if not attrs.get('phone'):
                raise serializers.ValidationError({'phone': 'Phone is required.'})
        return attrs


class VacateFlatSerializer(serializers.Serializer):
    advanceNote = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    depositReturned = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )


class MyTenancySerializer(serializers.Serializer):
    """Tenant-facing active/past tenancy card payload."""

    id = serializers.UUIDField()
    status = serializers.CharField()
    startDate = serializers.CharField()
    endDate = serializers.CharField(allow_null=True, required=False)
    deposit = serializers.FloatField(allow_null=True, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    flat = serializers.DictField()
    building = serializers.DictField()
    owner = serializers.DictField()


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
