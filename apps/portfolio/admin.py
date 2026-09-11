from django.contrib import admin

from core.admin import TimestampedModelAdmin
from portfolio.models import Building, Flat, Floor, Tenancy


class FloorInline(admin.TabularInline):
    model = Floor
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


class FlatInline(admin.TabularInline):
    model = Flat
    extra = 0
    fk_name = 'building'
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Building)
class BuildingAdmin(TimestampedModelAdmin):
    list_display = ('name', 'city', 'owner', 'total_floors', 'total_flats')
    list_filter = ('city',)
    search_fields = ('name', 'address', 'owner__phone')
    inlines = [FloorInline, FlatInline]


@admin.register(Floor)
class FloorAdmin(TimestampedModelAdmin):
    list_display = ('building', 'floor_number', 'name')
    list_filter = ('building__city',)
    search_fields = ('building__name', 'name')


@admin.register(Flat)
class FlatAdmin(TimestampedModelAdmin):
    list_display = (
        'flat_number',
        'building',
        'floor_number',
        'rent',
        'status',
    )
    list_filter = ('status', 'building__city')
    search_fields = ('flat_number', 'building__name')


@admin.register(Tenancy)
class TenancyAdmin(TimestampedModelAdmin):
    list_display = ('flat', 'tenant', 'status', 'start_date', 'end_date')
    list_filter = ('status',)
    search_fields = ('tenant__phone', 'tenant_name', 'flat__flat_number')
