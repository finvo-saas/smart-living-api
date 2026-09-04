"""Expire featured boosts, hide stale inventory, refresh hotel room counts."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from discovery.services.freshness import expire_featured
from hotels.models import Hotel
from mess.models import Mess


class Command(BaseCommand):
    help = 'Refresh public discovery: expire boosts and recount hotel rooms'

    def handle(self, *args, **options):
        expired = expire_featured()
        rooms = 0
        for hotel in Hotel.objects.filter(is_deleted=False):
            hotel.refresh_room_counts()
            rooms += 1
        seats = 0
        for mess in Mess.objects.filter(is_deleted=False):
            mess.refresh_seat_counts()
            seats += 1
        self.stdout.write(
            self.style.SUCCESS(
                f'expired_featured={expired} hotels_recounted={rooms} '
                f'messes_recounted={seats} at={timezone.now().isoformat()}',
            ),
        )
