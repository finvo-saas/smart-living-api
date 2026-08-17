from decimal import Decimal

from rest_framework import serializers

from listings.models import (
    ListingStatus,
    Property,
    PropertyImage,
    PropertyReview,
    PropertyType,
)


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


class PropertySerializer(serializers.ModelSerializer):
    ownerId = serializers.UUIDField(source='owner_id', read_only=True)
    ownerName = serializers.SerializerMethodField()
    ownerPhone = serializers.SerializerMethodField()
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
    rent = serializers.SerializerMethodField()

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
            'furnishing',
            'parking',
            'security',
            'verified',
            'verificationStatus',
            'verifiedAt',
            'description',
            'ownerId',
            'ownerName',
            'ownerPhone',
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
        )
        read_only_fields = (
            'id',
            'ownerId',
            'ownerName',
            'ownerPhone',
            'verified',
            'verificationStatus',
            'verifiedAt',
            'rating',
            'reviewCount',
            'createdAt',
            'updatedAt',
        )

    def get_ownerName(self, obj):
        return obj.owner.name or f'User {obj.owner.phone[-4:]}'

    def get_ownerPhone(self, obj):
        return obj.owner.phone

    def get_rent(self, obj):
        return _money(obj.rent)

    def get_mealCost(self, obj):
        if obj.meal_cost is None:
            return None
        return _money(obj.meal_cost)

    def get_images(self, obj):
        request = self.context.get('request')
        urls = list(obj.image_urls or [])
        for img in obj.image_files.all():
            resolved = img.resolved_url(request)
            if resolved:
                urls.append(resolved)
        return urls


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
            'facilities',
            'nearbyFacilities',
            'buildingAge',
            'floorLevel',
            'furnishing',
            'parking',
            'security',
            'description',
            'instantBook',
            'depositMonths',
            'published',
            'listingStatus',
        )

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Listing name is required')
        return value.strip()

    def validate_rent(self, value):
        if value is None or Decimal(value) < 500:
            raise serializers.ValidationError('Rent must be at least ৳500')
        return value

    def validate_description(self, value):
        if not value or len(value.strip()) < 20:
            raise serializers.ValidationError(
                'Description must be at least 20 characters',
            )
        return value.strip()

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
        for key in ('gender', 'seat_type', 'meal_plan', 'furnishing'):
            if key in attrs and attrs[key] == '':
                attrs[key] = None
        return attrs

    def create(self, validated_data):
        images = validated_data.pop('images', [])
        validated_data['image_urls'] = images
        validated_data.setdefault('verification_status', 'pending')
        if 'deposit_months' not in validated_data:
            validated_data['deposit_months'] = (
                2 if validated_data.get('type') == PropertyType.APARTMENT else 1
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        images = validated_data.pop('images', None)
        if images is not None:
            validated_data['image_urls'] = images
        return super().update(instance, validated_data)


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

    class Meta:
        model = PropertyReview
        fields = (
            'id',
            'propertyId',
            'userId',
            'userName',
            'userAvatar',
            'rating',
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
            request = self.context.get('request')
            url = obj.user.profile_photo.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None


class ReviewCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(min_length=10)
    stayDurationMonths = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
    )


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
