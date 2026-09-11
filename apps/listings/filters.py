import django_filters

from listings.models import Property


class PropertyFilter(django_filters.FilterSet):
    propertyType = django_filters.CharFilter(field_name='type')
    type = django_filters.CharFilter(field_name='type')
    city = django_filters.CharFilter(field_name='city', lookup_expr='iexact')
    area = django_filters.CharFilter(field_name='area', lookup_expr='iexact')
    rentMin = django_filters.NumberFilter(field_name='rent', lookup_expr='gte')
    rentMax = django_filters.NumberFilter(field_name='rent', lookup_expr='lte')
    availableOnly = django_filters.BooleanFilter(method='filter_available')
    gender = django_filters.CharFilter(method='filter_gender')
    seatType = django_filters.CharFilter(field_name='seat_type')
    mealIncluded = django_filters.BooleanFilter(field_name='meal_included')
    mealPlan = django_filters.CharFilter(field_name='meal_plan')
    furnishing = django_filters.CharFilter(field_name='furnishing')
    parking = django_filters.BooleanFilter(field_name='parking')
    security = django_filters.BooleanFilter(field_name='security')
    verifiedOnly = django_filters.BooleanFilter(method='filter_verified')
    buildingAge = django_filters.NumberFilter(
        field_name='building_age',
        lookup_expr='lte',
    )
    floorLevel = django_filters.NumberFilter(
        field_name='floor_level',
        lookup_expr='lte',
    )
    bedrooms = django_filters.NumberFilter(field_name='bedrooms', lookup_expr='gte')
    bathrooms = django_filters.NumberFilter(field_name='bathrooms', lookup_expr='gte')
    sizeSqftMin = django_filters.NumberFilter(field_name='size_sqft', lookup_expr='gte')
    sizeSqftMax = django_filters.NumberFilter(field_name='size_sqft', lookup_expr='lte')
    tenantType = django_filters.CharFilter(field_name='tenant_type')
    featured = django_filters.BooleanFilter(field_name='featured')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = Property
        fields = []

    def filter_available(self, queryset, name, value):
        if value:
            return queryset.filter(available=True)
        return queryset

    def filter_verified(self, queryset, name, value):
        if value:
            return queryset.filter(verified=True) | queryset.filter(
                verification_status='verified',
            )
        return queryset

    def filter_gender(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(gender__in=[value, 'mixed'])

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return (
            queryset.filter(name__icontains=value)
            | queryset.filter(area__icontains=value)
            | queryset.filter(city__icontains=value)
            | queryset.filter(description__icontains=value)
        )
