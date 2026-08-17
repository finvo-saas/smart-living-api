"""Seat assignment and student enrollment."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User, UserProfile
from accounts.phone import normalize_bd_phone
from core.exceptions import ConflictError, InvalidError, NotFoundError
from mess.models import Mess, MessStudent, Seat, SeatStatus


def _get_or_create_renter(phone: str, name: str, email: str = '') -> User:
    normalized = normalize_bd_phone(phone)
    user, created = User.objects.get_or_create(
        phone=normalized,
        defaults={
            'name': name.strip(),
            'email': email or '',
            'role': Role.RENTER,
            'is_phone_verified': True,
            'role_selected': True,
        },
    )
    if not created:
        updates = []
        if name.strip() and not user.name:
            user.name = name.strip()
            updates.append('name')
        if email and not user.email:
            user.email = email
            updates.append('email')
        if updates:
            user.save(update_fields=updates + ['updated_at'])
    UserProfile.objects.get_or_create(user=user)
    return user


def assign_student(mess: Mess, data: dict, *, link_user: User | None = None) -> MessStudent:
    name = data['name'].strip()
    phone = normalize_bd_phone(data['phone'])
    email = data.get('email', '') or ''
    student_id_code = data.get('studentId', '') or ''
    university = data.get('university', '') or ''
    seat_number = data.get('seatNumber', '') or ''
    monthly_fee = data.get('monthlyFee')
    if monthly_fee is None:
        monthly_fee = mess.monthly_fee

    user = link_user
    if not user:
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            user = None

    with transaction.atomic():
        student = MessStudent.objects.create(
            mess=mess,
            user=user,
            name=name,
            phone=phone,
            email=email,
            student_id_code=student_id_code,
            university=university,
            seat_number=seat_number,
            joined_date=date.today(),
            monthly_fee=Decimal(str(monthly_fee)),
            is_active=True,
        )

        if seat_number:
            try:
                seat = Seat.objects.select_for_update().get(
                    mess=mess,
                    seat_number=seat_number,
                    is_deleted=False,
                )
            except Seat.DoesNotExist as exc:
                raise NotFoundError(f'Seat {seat_number} not found.') from exc

            if seat.status == SeatStatus.OCCUPIED and seat.student_id:
                raise ConflictError(f'Seat {seat_number} is already occupied.')

            seat.status = SeatStatus.OCCUPIED
            seat.student = student
            seat.save(update_fields=['status', 'student', 'updated_at'])
            student.seat = seat
            student.seat_number = seat_number
            student.save(update_fields=['seat', 'seat_number', 'updated_at'])

        mess.refresh_seat_counts()

    return student
