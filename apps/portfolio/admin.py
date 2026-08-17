from django.contrib import admin

from portfolio.models import Building, Flat, Floor, Tenancy


class FloorInline(admin.TabularInline):
    model = Floor
    extra = 0


class FlatInline(admin.TabularInline):
    model = Flat
    extra = 0
    fk_name = 'building'


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'owner', 'total_floors', 'total_flats', 'created_at')
    list_filter = ('city',)
    search_fields = ('name', 'address', 'owner__phone')
    inlines = [FloorInline, FlatInline]


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ('building', 'floor_number', 'name', 'created_at')
    list_filter = ('building__city',)
    search_fields = ('building__name', 'name')


@admin.register(Flat)
class FlatAdmin(admin.ModelAdmin):
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
class TenancyAdmin(admin.ModelAdmin):
    list_display = ('flat', 'tenant', 'status', 'start_date', 'end_date')
    list_filter = ('status',)
    search_fields = ('tenant__phone', 'tenant_name', 'flat__flat_number')
