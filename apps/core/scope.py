"""Shared cross-vertical scope discriminator (billing-style)."""

from django.db import models


class ScopeType(models.TextChoices):
    """Ops root for shared features: notices, tickets, documents."""

    MESS = 'mess', 'Mess'
    BUILDING = 'building', 'Building / Apartment'
    HOTEL = 'hotel', 'Hotel'
