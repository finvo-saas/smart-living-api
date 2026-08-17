from rest_framework import serializers

from discovery.models import Favorite, SavedSearch, SearchHistory


class FavoriteSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    propertyId = serializers.UUIDField(source='property_id', read_only=True)
    propertyName = serializers.CharField(source='property.name', read_only=True)
    propertyType = serializers.CharField(source='property.type', read_only=True)
    propertyImage = serializers.SerializerMethodField()
    propertyRent = serializers.SerializerMethodField()
    propertyArea = serializers.CharField(source='property.area', read_only=True)
    propertyCity = serializers.CharField(source='property.city', read_only=True)
    addedAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Favorite
        fields = (
            'id',
            'userId',
            'propertyId',
            'propertyName',
            'propertyType',
            'propertyImage',
            'propertyRent',
            'propertyArea',
            'propertyCity',
            'addedAt',
            'notes',
        )

    def get_propertyImage(self, obj):
        urls = obj.property.image_urls or []
        if urls:
            return urls[0]
        request = self.context.get('request')
        img = obj.property.image_files.first()
        if img:
            return img.resolved_url(request)
        return ''

    def get_propertyRent(self, obj):
        return float(obj.property.rent)


class ToggleFavoriteSerializer(serializers.Serializer):
    propertyId = serializers.UUIDField()
    property_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        pid = attrs.get('propertyId') or attrs.get('property_id')
        if not pid:
            raise serializers.ValidationError({'propertyId': 'Required'})
        return {'propertyId': pid}


class SavedSearchSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    isActive = serializers.BooleanField(source='is_active')
    lastChecked = serializers.DateTimeField(source='last_checked', allow_null=True)
    matchCount = serializers.IntegerField(source='match_count')
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = SavedSearch
        fields = (
            'id',
            'userId',
            'name',
            'filters',
            'isActive',
            'lastChecked',
            'matchCount',
            'createdAt',
            'updatedAt',
        )


class SavedSearchWriteSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', required=False)
    matchCount = serializers.IntegerField(source='match_count', required=False)
    lastChecked = serializers.DateTimeField(
        source='last_checked',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = SavedSearch
        fields = ('name', 'filters', 'isActive', 'matchCount', 'lastChecked')

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Name is required')
        return value.strip()


class SearchHistorySerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    searchQuery = serializers.CharField(source='search_query')
    resultCount = serializers.IntegerField(source='result_count')
    searchedAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = SearchHistory
        fields = (
            'id',
            'userId',
            'searchQuery',
            'filters',
            'resultCount',
            'searchedAt',
        )


class SearchHistoryWriteSerializer(serializers.Serializer):
    searchQuery = serializers.CharField(required=False, allow_blank=True, default='')
    filters = serializers.JSONField(required=False, default=dict)
    resultCount = serializers.IntegerField(required=False, default=0)

    def create(self, validated_data):
        return SearchHistory.objects.create(
            user=self.context['request'].user
            if 'request' in self.context
            else validated_data.pop('user', None),
            search_query=validated_data.get('searchQuery', ''),
            filters=validated_data.get('filters') or {},
            result_count=validated_data.get('resultCount') or 0,
        )
