"""Fill map pin and nearby places after a listing is saved.

Geocoding and Overpass can take a minute when the public APIs are slow.
They must not run inside the create/update request, or the browser times out
and the owner sees HTTP 500.
"""
from __future__ import annotations

import logging
import threading

from django.db import close_old_connections, transaction

logger = logging.getLogger(__name__)


def schedule_place_enrichment(prop_id, *, geocode: bool) -> None:
    def _start() -> None:
        threading.Thread(
            target=_enrich,
            args=(str(prop_id), geocode),
            daemon=True,
            name='listing-place-enrich',
        ).start()

    transaction.on_commit(_start)


def _enrich(prop_id: str, geocode: bool) -> None:
    close_old_connections()
    try:
        from listings.models import Property
        from listings.services.poi_enrich import refresh_nearby_facilities

        listing = Property.objects.filter(pk=prop_id).first()
        if listing is None:
            return
        if geocode:
            from discovery.services.geocode import (
                ensure_property_coordinates,
                refresh_property_coordinates,
            )

            if listing.latitude is None or listing.longitude is None:
                ensure_property_coordinates(listing)
            else:
                refresh_property_coordinates(listing)
            listing.refresh_from_db()
        if listing.latitude is None or listing.longitude is None:
            return
        if geocode or not listing.nearby_facilities:
            refresh_nearby_facilities(listing)
    except Exception:
        logger.exception('Listing place enrichment failed for %s', prop_id)
    finally:
        close_old_connections()
