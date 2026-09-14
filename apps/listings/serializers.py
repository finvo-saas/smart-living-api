import re
from decimal import Decimal

from rest_framework import serializers

from discovery.services.freshness import freshness_dict
from listings.models import (
    ListingStatus,
    Property,
    PropertyImage,
    PropertyReview,
    PropertyType,
)

_TAG_RE = re.compile(r'<[^>]+>')


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _bill(value):
    if value is None:
        return None
    return _money(value)


def _plain_text(value: str) -> str:
    return _TAG_RE.sub(' ', value or '').replace('&nbsp;', ' ').strip()


class PropertySerializer(serializers.ModelSerializer):
    ownerId = serializers.UUIDField(source='owner_id', read_only=True)
    ownerName = serializers.SerializerMethodField()
    ownerPhone = serializers.SerializerMethodField()
    ownerWhatsapp = serializers.SerializerMethodField()
    seatType = serializers.CharField(source='seat_type', allow_null=True, required=False)
    mealIncluded = serializers.BooleanField(
        source='meal_included',
        allow_null=True,
        required=False,
    )
    mealPlan = serializers.CharField(source='meal_plan', allow_null=True, required=False)
    mealCost = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    videoThumbnail = serializers.CharField(
        source='video_thumbnail',
        allow_blank=True,
        required=False,
    )
    nearbyFacilities = serializers.JSONField(
        source='nearby_facilities',
        required=False,
    )
    buildingAge = serializers.IntegerField(
        source='building_age',
        allow_null=True,
        required=False,
    )
    floorLevel = serializers.IntegerField(
        source='floor_level',
        allow_null=True,
        required=False,
    )
    bedrooms = serializers.IntegerField(allow_null=True, required=False)
    bathrooms = serializers.IntegerField(allow_null=True, required=False)
    kitchens = serializers.IntegerField(allow_null=True, required=False)
    livingRooms = serializers.IntegerField(
        source='living_rooms',
        allow_null=True,
        required=False,
    )
    balconies = serializers.IntegerField(allow_null=True, required=False)
    sizeSqft = serializers.IntegerField(
        source='size_sqft',
        allow_null=True,
        required=False,
    )
    unitNumber = serializers.CharField(
        source='unit_number',
        allow_blank=True,
        required=False,
    )
    propertyFace = serializers.CharField(
        source='property_face',
        allow_null=True,
        required=False,
    )
    serviceCharge = serializers.SerializerMethodField()
    electricityBill = serializers.SerializerMethodField()
    gasBill = serializers.SerializerMethodField()
    internetBill = serializers.SerializerMethodField()
    waterBill = serializers.SerializerMethodField()
    parkingCount = serializers.IntegerField(
        source='parking_count',
        allow_null=True,
        required=False,
    )
    availableFrom = serializers.DateField(
        source='available_from',
        allow_null=True,
        required=False,
    )
    rentNegotiable = serializers.BooleanField(
        source='rent_negotiable',
        required=False,
    )
    tenantType = serializers.CharField(
        source='tenant_type',
        allow_null=True,
        required=False,
    )
    verificationStatus = serializers.CharField(source='verification_status')
    verifiedAt = serializers.DateTimeField(source='verified_at', allow_null=True)
    instantBook = serializers.BooleanField(source='instant_book', required=False)
    depositMonths = serializers.IntegerField(source='deposit_months', required=False)
    listingStatus = serializers.CharField(source='listing_status', required=False)
    reviewCount = serializers.IntegerField(source='review_count', read_only=True)
    featuredUntil = serializers.DateTimeField(
        source='featured_until',
        allow_null=True,
        required=False,
    )
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    lastConfirmedAt = serializers.DateTimeField(
        source='last_confirmed_at',
        allow_null=True,
        read_only=True,
    )
    rent = serializers.SerializerMethodField()
    confirmedHoursAgo = serializers.SerializerMethodField()
    stale = serializers.SerializerMethodField()
    openSeats = serializers.IntegerField(source='open_seats', allow_null=True, read_only=True)
    verificationScore = serializers.SerializerMethodField()
    livingCost = serializers.SerializerMethodField()
    livingConditionScore = serializers.SerializerMethodField()
    safetyScore = serializers.SerializerMethodField()
    messId = serializers.SerializerMethodField()
    linkedFlatId = serializers.SerializerMethodField()
    utilities = serializers.SerializerMethodField()
    tourImages = serializers.JSONField(source='tour_images', required=False)
    cctv = serializers.BooleanField(allow_null=True, required=False)
    streetLighting = serializers.BooleanField(
        source='street_lighting',
        allow_null=True,
        required=False,
    )
    addressVerified = serializers.BooleanField(source='address_verified', read_only=True)
    photosVerified = serializers.BooleanField(source='photos_verified', read_only=True)
    rentVerified = serializers.BooleanField(source='rent_verified', read_only=True)

    class Meta:
        model = Property
        fields = (
            'id',
            'name',
            'type',
            'rent',
            'area',
            'address',
            'city',
            'latitude',
            'longitude',
            'available',
            'gender',
            'seatType',
            'mealIncluded',
            'mealPlan',
            'mealCost',
            'images',
            'videos',
            'videoThumbnail',
            'facilities',
            'nearbyFacilities',
            'buildingAge',
            'floorLevel',
            'bedrooms',
            'bathrooms',
            'kitchens',
            'livingRooms',
            'balconies',
            'sizeSqft',
            'unitNumber',
            'propertyFace',
            'serviceCharge',
            'electricityBill',
            'gasBill',
            'internetBill',
            'waterBill',
            'parkingCount',
            'availableFrom',
            'rentNegotiable',
            'tenantType',
            'furnishing',
            'parking',
            'security',
            'verified',
            'verificationStatus',
            'verifiedAt',
            'addressVerified',
            'photosVerified',
            'rentVerified',
            'description',
            'ownerId',
            'ownerName',
            'ownerPhone',
            'ownerWhatsapp',
            'createdAt',
            'instantBook',
            'depositMonths',
            'published',
            'listingStatus',
            'rating',
            'reviewCount',
            'updatedAt',
            'featured',
            'featuredUntil',
            'lastConfirmedAt',
            'confirmedHoursAgo',
            'stale',
            'openSeats',
            'verificationScore',
            'livingCost',
            'livingConditionScore',
            'safetyScore',
            'messId',
            'linkedFlatId',
            'utilities',
            'tourImages',
            'cctv',
            'streetLighting',
        )
        read_only_fields = (
            'id',
            'ownerId',
            'ownerName',
            'ownerPhone',
            'ownerWhatsapp',
            'verified',
            'verificationStatus',
            'verifiedAt',
            'addressVerified',
            'photosVerified',
            'rentVerified',
            'rating',
            'reviewCount',
            'createdAt',
            'updatedAt',
            'openSeats',
            'verificationScore',
            'livingCost',
            'livingConditionScore',
            'safetyScore',
            'messId',
            'utilities',
        )

    def get_ownerName(self, obj):
        return obj.owner.name or f'User {obj.owner.phone[-4:]}'

    def get_ownerPhone(self, obj):
        return obj.owner.phone

    def get_ownerWhatsapp(self, obj) -> str:
        return obj.owner.whatsapp_number or ''

    def get_serviceCharge(self, obj):
        if obj.service_charge is None:
            return None
        return _money(obj.service_charge)

    def get_rent(self, obj):
        return _money(obj.rent)

    def get_confirmedHoursAgo(self, obj):
        return freshness_dict(obj)['confirmedHoursAgo']

    def get_stale(self, obj):
        return freshness_dict(obj)['stale']

    def get_mealCost(self, obj):
        if obj.meal_cost is None:
            return None
        return _money(obj.meal_cost)

    def get_electricityBill(self, obj):
        return _bill(obj.electricity_bill)

    def get_gasBill(self, obj):
        return _bill(obj.gas_bill)

    def get_internetBill(self, obj):
        return _bill(obj.internet_bill)

    def get_waterBill(self, obj):
        return _bill(obj.water_bill)

    def get_images(self, obj):
        request = self.context.get('request')
        urls = list(obj.image_urls or [])
        for img in obj.image_files.all():
            resolved = img.resolved_url(request)
            if resolved:
                urls.append(resolved)
        return urls

    def get_verificationScore(self, obj):
        from listings.services.verification_score import verification_payload

        return verification_payload(obj)

    def get_livingCost(self, obj):
        from listings.services.living_cost import living_cost_for_property

        return living_cost_for_property(obj)

    def get_livingConditionScore(self, obj):
        from listings.services.living_condition import living_condition_for_property

        return living_condition_for_property(obj)

    def get_safetyScore(self, obj):
        from listings.services.safety_score import safety_score_for_property

        return safety_score_for_property(obj)

    def _linked_mess(self, obj):
        linked = getattr(obj, 'linked_messes', None)
        if linked is None:
            return None
        return linked.filter(is_deleted=False).first()

    def get_messId(self, obj):
        mess = self._linked_mess(obj)
        return str(mess.id) if mess is not None else None

    def _apartment_flat(self, obj):
        if obj.type != PropertyType.APARTMENT:
            return None
        flats = list(obj.linked_flats.all())
        if not flats:
            return None
        return min(flats, key=lambda flat: flat.created_at)

    def get_linkedFlatId(self, obj):
        flat = self._apartment_flat(obj)
        return str(flat.id) if flat is not None else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.type != PropertyType.APARTMENT:
            return data
        from listings.services.inventory import apartment_is_bookable

        bookable = apartment_is_bookable(instance)
        data['available'] = bookable
        if not bookable:
            data['instantBook'] = False
        flat = self._apartment_flat(instance)
        if flat is None:
            data['occupancy'] = 'unlinked'
            data['unitLabel'] = None
            data['flatStatus'] = None
            return data
        data['occupancy'] = 'vacant' if flat.status == 'available' else 'occupied'
        building = getattr(flat, 'building', None)
        building_name = getattr(building, 'name', '') or ''
        data['unitLabel'] = (
            f'{building_name} · Flat {flat.flat_number}'.strip(' ·')
            if building_name
            else f'Flat {flat.flat_number}'
        )
        data['flatStatus'] = flat.status
        return data

    def get_utilities(self, obj):
        mess = self._linked_mess(obj)
        if mess is None:
            return None
        from mess.services.reliability import reliability_bundle

        return reliability_bundle(mess)


class PropertyWriteSerializer(serializers.ModelSerializer):
    seatType = serializers.CharField(
        source='seat_type',
        allow_null=True,
        required=False,
        allow_blank=True,
    )
    mealIncluded = serializers.BooleanField(
        source='meal_included',
        allow_null=True,
        required=False,
    )
    mealPlan = serializers.CharField(
        source='meal_plan',
        allow_null=True,
        required=False,
        allow_blank=True,
    )
    mealCost = serializers.DecimalField(
        source='meal_cost',
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    images = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=list,
    )
    videoThumbnail = serializers.CharField(
        source='video_thumbnail',
        required=False,
        allow_blank=True,
    )
    nearbyFacilities = serializers.ListField(
        child=serializers.CharField(),
        source='nearby_facilities',
        required=False,
        default=list,
    )
    buildingAge = serializers.IntegerField(
        source='building_age',
        allow_null=True,
        required=False,
    )
    floorLevel = serializers.IntegerField(
        source='floor_level',
        allow_null=True,
        required=False,
    )
    bedrooms = serializers.IntegerField(allow_null=True, required=False)
    bathrooms = serializers.IntegerField(allow_null=True, required=False)
    kitchens = serializers.IntegerField(allow_null=True, required=False)
    livingRooms = serializers.IntegerField(
        source='living_rooms',
        allow_null=True,
        required=False,
    )
    balconies = serializers.IntegerField(allow_null=True, required=False)
    sizeSqft = serializers.IntegerField(
        source='size_sqft',
        allow_null=True,
        required=False,
    )
    unitNumber = serializers.CharField(
        source='unit_number',
        required=False,
        allow_blank=True,
    )
    propertyFace = serializers.CharField(
        source='property_face',
        allow_null=True,
        required=False,
        allow_blank=True,
    )
    serviceCharge = serializers.DecimalField(
        source='service_charge',
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    electricityBill = serializers.DecimalField(
        source='electricity_bill',
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    gasBill = serializers.DecimalField(
        source='gas_bill',
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    internetBill = serializers.DecimalField(
        source='internet_bill',
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    waterBill = serializers.DecimalField(
        source='water_bill',
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    parkingCount = serializers.IntegerField(
        source='parking_count',
        allow_null=True,
        required=False,
    )
    availableFrom = serializers.DateField(
        source='available_from',
        allow_null=True,
        required=False,
    )
    rentNegotiable = serializers.BooleanField(
        source='rent_negotiable',
        required=False,
    )
    tenantType = serializers.CharField(
        source='tenant_type',
        allow_null=True,
        required=False,
        allow_blank=True,
    )
    instantBook = serializers.BooleanField(source='instant_book', required=False)
    depositMonths = serializers.IntegerField(source='deposit_months', required=False)
    listingStatus = serializers.ChoiceField(
        source='listing_status',
        choices=ListingStatus.choices,
        required=False,
    )
    facilities = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    videos = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        default=list,
    )
    tourImages = serializers.ListField(
        child=serializers.URLField(),
        source='tour_images',
        required=False,
        default=list,
    )
    cctv = serializers.BooleanField(allow_null=True, required=False)
    streetLighting = serializers.BooleanField(
        source='street_lighting',
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Property
        fields = (
            'name',
            'type',
            'rent',
            'area',
            'address',
            'city',
            'latitude',
            'longitude',
            'available',
            'gender',
            'seatType',
            'mealIncluded',
            'mealPlan',
            'mealCost',
            'images',
            'videos',
            'videoThumbnail',
            'tourImages',
            'facilities',
            'nearbyFacilities',
            'buildingAge',
            'floorLevel',
            'bedrooms',
            'bathrooms',
            'kitchens',
            'livingRooms',
            'balconies',
            'sizeSqft',
            'unitNumber',
            'propertyFace',
            'serviceCharge',
            'electricityBill',
            'gasBill',
            'internetBill',
            'waterBill',
            'parkingCount',
            'availableFrom',
            'rentNegotiable',
            'tenantType',
            'furnishing',
            'parking',
            'security',
            'cctv',
            'streetLighting',
            'description',
            'instantBook',
            'depositMonths',
            'published',
            'listingStatus',
            'flatId',
        )

    flatId = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Listing name is required')
        return value.strip()

    def validate_rent(self, value):
        if value is None or Decimal(value) < 500:
            raise serializers.ValidationError('Rent must be at least ৳500')
        return value

    def validate_description(self, value):
        plain = _plain_text(value or '')
        if len(plain) < 20:
            raise serializers.ValidationError(
                'Description must be at least 20 characters',
            )
        return (value or '').strip()

    def validate(self, attrs):
        images = attrs.get('images', serializers.empty)
        if images is not serializers.empty and not images:
            raise serializers.ValidationError({'images': 'Add at least one photo'})
        if self.instance is None and not attrs.get('images'):
            # images may come as write-only list mapped to image_urls
            pass
        city = attrs.get('city', getattr(self.instance, 'city', ''))
        area = attrs.get('area', getattr(self.instance, 'area', ''))
        if not str(city).strip() or not str(area).strip():
            raise serializers.ValidationError('City and area are required')

        listing_status = attrs.get('listing_status')
        published = attrs.get('published')
        if listing_status == ListingStatus.PUBLISHED:
            attrs['published'] = True
        elif listing_status in (ListingStatus.DRAFT, ListingStatus.PAUSED):
            attrs['published'] = False
        elif published is True and listing_status is None:
            attrs['listing_status'] = ListingStatus.PUBLISHED
        elif published is False and listing_status is None:
            attrs.setdefault('listing_status', ListingStatus.DRAFT)

        # Normalize empty strings to None for nullable choices
        for key in (
            'gender',
            'seat_type',
            'meal_plan',
            'furnishing',
            'tenant_type',
            'property_face',
        ):
            if key in attrs and attrs[key] == '':
                attrs[key] = None

        if 'parking_count' in attrs and attrs['parking_count'] is not None:
            attrs['parking'] = attrs['parking_count'] > 0

        self._require_vacant_flat(attrs)
        return attrs

    def _require_vacant_flat(self, attrs):
        listing_type = attrs.get('type', getattr(self.instance, 'type', None))
        if listing_type != PropertyType.APARTMENT:
            return
        published = attrs.get('published', getattr(self.instance, 'published', False))
        from portfolio.models import Flat, FlatStatus

        flat_id = attrs.get('flatId')
        if flat_id is None and published and self.instance is not None:
            linked = self.instance.linked_flats.order_by('created_at').first()
            flat_id = linked.id if linked else None
        if flat_id is None:
            if published:
                raise serializers.ValidationError(
                    {'flatId': 'Choose a vacant flat from My properties before publishing.'},
                )
            return
        owner_id = getattr(self.instance, 'owner_id', None)
        request = self.context.get('request')
        if owner_id is None and request is not None:
            owner_id = request.user.id
        flat = (
            Flat.objects.select_related('building')
            .filter(pk=flat_id, building__owner_id=owner_id)
            .first()
        )
        if flat is None:
            raise serializers.ValidationError({'flatId': 'That flat is not in your buildings.'})
        if flat.listing_id and (self.instance is None or flat.listing_id != self.instance.id):
            raise serializers.ValidationError(
                {'flatId': 'This flat already has a listing. Edit that listing instead.'},
            )
        already_linked = (
            self.instance is not None and flat.listing_id == self.instance.id
        )
        if published and flat.status != FlatStatus.AVAILABLE and not already_linked:
            raise serializers.ValidationError(
                {'flatId': 'That flat is not vacant. Vacate it before publishing.'},
            )

    def _bind_flat(self, prop, flat_id):
        if not flat_id or prop.type != PropertyType.APARTMENT:
            return
        from portfolio.models import Flat
        from listings.services.inventory import bind_listing_to_flat

        flat = Flat.objects.filter(pk=flat_id, building__owner_id=prop.owner_id).first()
        if flat is None:
            return
        bind_listing_to_flat(prop, flat)

    def create(self, validated_data):
        images = validated_data.pop('images', [])
        flat_id = validated_data.pop('flatId', None)
        validated_data['image_urls'] = images
        validated_data.setdefault('verification_status', 'pending')
        if 'deposit_months' not in validated_data:
            validated_data['deposit_months'] = (
                2 if validated_data.get('type') == PropertyType.APARTMENT else 1
            )
        prop = super().create(validated_data)
        from listings.services.inventory import link_listing_to_mess, push_listing_bills_to_flat
        from listings.services.place_enrich import (
            apply_listing_pin,
            schedule_place_enrichment,
        )

        link_listing_to_mess(prop)
        self._bind_flat(prop, flat_id)
        push_listing_bills_to_flat(prop)
        apply_listing_pin(prop, force=False)
        schedule_place_enrichment(
            prop.pk,
            geocode=prop.latitude is None or prop.longitude is None,
        )
        return prop

    def update(self, instance, validated_data):
        images = validated_data.pop('images', None)
        flat_id = validated_data.pop('flatId', None)
        if images is not None:
            validated_data['image_urls'] = images
        tour = validated_data.pop('tour_images', serializers.empty)
        if tour is not serializers.empty:
            validated_data['tour_images'] = tour
        previous_place = (instance.address, instance.city, instance.area)
        prop = super().update(instance, validated_data)
        from listings.services.inventory import push_listing_bills_to_flat
        from listings.services.place_enrich import (
            apply_listing_pin,
            schedule_place_enrichment,
        )

        self._bind_flat(prop, flat_id)
        push_listing_bills_to_flat(prop)
        address_changed = (prop.address, prop.city, prop.area) != previous_place
        missing_pin = prop.latitude is None or prop.longitude is None
        if address_changed or missing_pin:
            apply_listing_pin(prop, force=address_changed)
        missing_pin = prop.latitude is None or prop.longitude is None
        if address_changed or missing_pin or not prop.nearby_facilities:
            schedule_place_enrichment(prop.pk, geocode=missing_pin)
        return prop


class PropertyReviewSerializer(serializers.ModelSerializer):
    propertyId = serializers.UUIDField(source='property_id', read_only=True)
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.SerializerMethodField()
    userAvatar = serializers.SerializerMethodField()
    stayDurationMonths = serializers.IntegerField(
        source='stay_duration_months',
        allow_null=True,
        required=False,
    )
    verifiedStay = serializers.BooleanField(source='verified_stay', read_only=True)
    ownerResponse = serializers.CharField(source='owner_response', read_only=True)
    ownerResponseDate = serializers.DateTimeField(
        source='owner_response_date',
        read_only=True,
        allow_null=True,
    )
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    ownerBehaviour = serializers.IntegerField(
        source='owner_behaviour',
        allow_null=True,
        read_only=True,
    )
    valueForMoney = serializers.IntegerField(
        source='value_for_money',
        allow_null=True,
        read_only=True,
    )

    class Meta:
        model = PropertyReview
        fields = (
            'id',
            'propertyId',
            'userId',
            'userName',
            'userAvatar',
            'rating',
            'cleanliness',
            'security',
            'ownerBehaviour',
            'location',
            'valueForMoney',
            'comment',
            'images',
            'createdAt',
            'ownerResponse',
            'ownerResponseDate',
            'stayDurationMonths',
            'verifiedStay',
        )
        read_only_fields = fields

    def get_userName(self, obj):
        return obj.user.name or f'User {obj.user.phone[-4:]}'

    def get_userAvatar(self, obj):
        if obj.user.profile_photo:
            from core.services.media import media_storage

            return media_storage.absolute_url(
                obj.user.profile_photo.url,
                request=self.context.get('request'),
            )
        return None


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    comment = serializers.CharField(min_length=10)
    stayDurationMonths = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
    )
    cleanliness = serializers.IntegerField(min_value=1, max_value=5, required=False)
    security = serializers.IntegerField(min_value=1, max_value=5, required=False)
    ownerBehaviour = serializers.IntegerField(min_value=1, max_value=5, required=False)
    location = serializers.IntegerField(min_value=1, max_value=5, required=False)
    valueForMoney = serializers.IntegerField(min_value=1, max_value=5, required=False)

    def validate(self, attrs):
        categories = [
            attrs.get('cleanliness'),
            attrs.get('security'),
            attrs.get('ownerBehaviour'),
            attrs.get('location'),
            attrs.get('valueForMoney'),
        ]
        filled = [v for v in categories if v is not None]
        rating = attrs.get('rating')
        if filled:
            attrs['rating'] = rating or int(round(sum(filled) / len(filled)))
        elif not rating:
            raise serializers.ValidationError(
                'Provide an overall rating or category ratings.',
            )
        return attrs


class OwnerResponseSerializer(serializers.Serializer):
    response = serializers.CharField(min_length=1)


class PropertyImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ('id', 'file', 'url', 'sort_order', 'alt_text')


class BatchIdsSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )
