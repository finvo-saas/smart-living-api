from django.conf import settings
from django.db import models
from django.db.models import Max

from core.models import TimestampedModel, UUIDModel


class FlatStatus(models.TextChoices):
    AVAILABLE = 'available', 'Available'
    OCCUPIED = 'occupied', 'Occupied'
    MAINTENANCE = 'maintenance', 'Maintenance'


class TenancyStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    ENDED = 'ended', 'Ended'
    PENDING = 'pending', 'Pending'


class Building(UUIDModel, TimestampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buildings',
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=80, db_index=True)
    total_floors = models.PositiveSmallIntegerField(default=1)
    total_flats = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'portfolio_building'
        ordering = ('-created_at',)

    def __str__(self):
        return self.name

    @property
    def occupied_flats(self) -> int:
        return self.flats.filter(status=FlatStatus.OCCUPIED).count()

    def refresh_counts(self):
        self.total_flats = self.flats.count()
        floor_max = self.floors.aggregate(m=Max('floor_number'))['m']
        if floor_max is not None:
            self.total_floors = floor_max
        self.save(update_fields=['total_flats', 'total_floors', 'updated_at'])


class Floor(UUIDModel, TimestampedModel):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name='floors',
    )
    floor_number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=120, blank=True, default='')
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'portfolio_floor'
        ordering = ('floor_number',)
        constraints = [
            models.UniqueConstraint(
                fields=['building', 'floor_number'],
                name='unique_floor_per_building',
            ),
        ]

    def __str__(self):
        return f'{self.building.name} F{self.floor_number}'


class Flat(UUIDModel, TimestampedModel):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name='flats',
    )
    floor = models.ForeignKey(
        Floor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='flats',
    )
    flat_number = models.CharField(max_length=40)
    floor_number = models.PositiveSmallIntegerField(default=1)
    rent = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=FlatStatus.choices,
        default=FlatStatus.AVAILABLE,
    )
    area = models.PositiveIntegerField(null=True, blank=True)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    listing = models.ForeignKey(
        'listings.Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_flats',
    )

    class Meta:
        db_table = 'portfolio_flat'
        ordering = ('floor_number', 'flat_number')
        constraints = [
            models.UniqueConstraint(
                fields=['building', 'flat_number'],
                name='unique_flat_number_per_building',
            ),
        ]

    def __str__(self):
        return f'{self.building.name} {self.flat_number}'


class Tenancy(UUIDModel, TimestampedModel):
    flat = models.ForeignKey(
        Flat,
        on_delete=models.CASCADE,
        related_name='tenancies',
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tenancies',
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    deposit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    agreement_ref = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=TenancyStatus.choices,
        default=TenancyStatus.ACTIVE,
    )
    # Snapshot fields for UI Renter embed when tenant has incomplete profile
    tenant_name = models.CharField(max_length=255, blank=True, default='')
    tenant_phone = models.CharField(max_length=20, blank=True, default='')
    tenant_email = models.EmailField(blank=True, default='')
    tenant_nid = models.CharField(max_length=40, blank=True, default='')
    tenant_address = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        db_table = 'portfolio_tenancy'
        ordering = ('-start_date',)
        indexes = [
            models.Index(fields=['status', 'flat']),
        ]

    def __str__(self):
        return f'{self.flat_id}:{self.tenant_id}:{self.status}'
