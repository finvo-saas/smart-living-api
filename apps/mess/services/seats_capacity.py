"""Seat inventory helpers for mess create/edit."""

from __future__ import annotations

from mess.models import Seat, SeatStatus


def ensure_seat_capacity(mess, target: int) -> None:
    """
    Grow/shrink available seat rows to match the owner's intended capacity.
    Never deletes occupied seats; soft-deletes spare available seats only.
    """
    target = max(0, min(int(target or 0), 200))
    seats = list(
        mess.seats.filter(is_deleted=False).order_by('room_number', 'seat_number'),
    )
    current = len(seats)

    if target > current:
        existing_numbers = {s.seat_number for s in seats}
        n = current
        i = 1
        while n < target:
            number = f'S{i}'
            i += 1
            if number in existing_numbers:
                continue
            Seat.objects.create(
                mess=mess,
                seat_number=number,
                room_number=f'R{(n // 2) + 1}',
                status=SeatStatus.AVAILABLE,
            )
            existing_numbers.add(number)
            n += 1
    elif target < current:
        removable = [
            s
            for s in reversed(seats)
            if s.status == SeatStatus.AVAILABLE and s.student_id is None
        ]
        for seat in removable[: current - target]:
            seat.is_deleted = True
            seat.save(update_fields=['is_deleted', 'updated_at'])

    mess.refresh_seat_counts()
