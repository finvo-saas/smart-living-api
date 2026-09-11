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
from mess.services.identity import (
    apply_member_photo,
    sync_linked_user_identity,
)


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


# Payload key → model field for the editable member profile.
PROFILE_FIELDS = {
    'whatsappNumber': 'whatsapp_number',
    'email': 'email',
    'occupantType': 'occupant_type',
    'photoUrl': 'photo_url',
    'studentId': 'student_id_code',
    'university': 'university',
    'organization': 'organization',
    'designation': 'designation',
    'emergencyContactName': 'emergency_contact_name',
    'emergencyContactPhone': 'emergency_contact_phone',
    'nidNumber': 'nid_number',
    'permanentAddress': 'permanent_address',
    'notes': 'notes',
}


def _claim_seat(mess: Mess, seat_number: str, student: MessStudent) -> Seat:
    try:
        seat = Seat.objects.select_for_update().get(
            mess=mess,
            seat_number=seat_number,
            is_deleted=False,
        )
    except Seat.DoesNotExist as exc:
        raise NotFoundError(f'Seat {seat_number} not found.') from exc

    if seat.student_id and seat.student_id != student.id:
        raise ConflictError(f'Seat {seat_number} is already occupied.')

    seat.status = SeatStatus.OCCUPIED
    seat.student = student
    seat.save(update_fields=['status', 'student', 'updated_at'])
    return seat


def _release_seat(student: MessStudent) -> None:
    """Free whichever seat this member currently holds."""
    seat = Seat.objects.select_for_update().filter(student=student).first()
    if seat:
        seat.student = None
        seat.status = SeatStatus.AVAILABLE
        seat.save(update_fields=['student', 'status', 'updated_at'])
    student.seat = None
    student.seat_number = ''


def assign_student(mess: Mess, data: dict, *, link_user: User | None = None) -> MessStudent:
    name = data['name'].strip()
    phone = normalize_bd_phone(data['phone'])
    seat_number = data.get('seatNumber', '') or ''
    monthly_fee = data.get('monthlyFee')
    if monthly_fee is None:
        monthly_fee = mess.monthly_fee
    joined_date = data.get('joinedDate') or date.today()

    user = link_user
    if not user:
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            user = None

    profile = {
        field: data[key] or ''
        for key, field in PROFILE_FIELDS.items()
        if data.get(key) is not None and key != 'photoUrl'
    }
    # Fall back to the linked account's WhatsApp number when left empty.
    if not profile.get('whatsapp_number') and user is not None:
        profile['whatsapp_number'] = user.whatsapp_number

    photo_url = data.get('photoUrl')

    with transaction.atomic():
        student = MessStudent.objects.create(
            mess=mess,
            user=user,
            name=name,
            phone=phone,
            seat_number=seat_number,
            joined_date=joined_date,
            monthly_fee=Decimal(str(monthly_fee)),
            is_active=True,
            **profile,
        )

        if seat_number:
            student.seat = _claim_seat(mess, seat_number, student)
            student.save(update_fields=['seat', 'updated_at'])

        if photo_url is not None:
            apply_member_photo(student, photo_url)
        if user is not None:
            sync_linked_user_identity(
                student,
                name=name,
                email=profile.get('email'),
                whatsapp=profile.get('whatsapp_number'),
            )

        mess.refresh_seat_counts()

    return student


def update_student(student: MessStudent, data: dict) -> MessStudent:
    """Owner edit of one member: profile, seat move, and move-out lifecycle."""
    mess = student.mess
    updates: set[str] = set()
    photo_url = data.get('photoUrl') if 'photoUrl' in data else None

    with transaction.atomic():
        student = MessStudent.objects.select_for_update().select_related('user').get(
            pk=student.pk,
        )

        if data.get('name'):
            student.name = data['name'].strip()
            updates.add('name')
        if data.get('phone'):
            student.phone = normalize_bd_phone(data['phone'])
            updates.add('phone')
            # Re-link if phone now matches an account.
            try:
                matched = User.objects.get(phone=student.phone)
            except User.DoesNotExist:
                matched = None
            if matched and student.user_id != matched.id:
                student.user = matched
                updates.add('user')
        for key, field in PROFILE_FIELDS.items():
            if key == 'photoUrl':
                continue
            if key in data and data[key] is not None:
                setattr(student, field, data[key] or '')
                updates.add(field)
        if data.get('monthlyFee') is not None:
            student.monthly_fee = Decimal(str(data['monthlyFee']))
            updates.add('monthly_fee')
        if data.get('joinedDate'):
            student.joined_date = data['joinedDate']
            updates.add('joined_date')

        is_active = data.get('isActive')
        seat_number = data.get('seatNumber')
        # Moving out or explicitly clearing the seat both release the seat.
        vacate = bool(data.get('vacateSeat')) or is_active is False

        if is_active is not None and is_active != student.is_active:
            student.is_active = is_active
            updates.add('is_active')
            if is_active:
                student.left_date = None
            else:
                student.left_date = data.get('leftDate') or date.today()
            updates.add('left_date')
        elif 'leftDate' in data:
            student.left_date = data['leftDate']
            updates.add('left_date')

        if vacate:
            _release_seat(student)
            updates.update({'seat', 'seat_number'})
        elif seat_number is not None and seat_number != student.seat_number:
            _release_seat(student)
            if seat_number:
                student.seat = _claim_seat(mess, seat_number, student)
                student.seat_number = seat_number
            updates.update({'seat', 'seat_number'})

        if updates:
            student.save(update_fields=[*updates, 'updated_at'])

        if photo_url is not None:
            apply_member_photo(student, photo_url)

        if student.user_id:
            sync_linked_user_identity(
                student,
                name=student.name if 'name' in updates else None,
                email=student.email if 'email' in updates else None,
                whatsapp=(
                    student.whatsapp_number
                    if 'whatsapp_number' in updates
                    else None
                ),
            )

        mess.refresh_seat_counts()

    return student


def remove_student(student: MessStudent) -> MessStudent:
    """Soft delete: the seat is freed but attendance/billing history stays."""
    with transaction.atomic():
        student = MessStudent.objects.select_for_update().get(pk=student.pk)
        _release_seat(student)
        student.is_active = False
        student.is_deleted = True
        if not student.left_date:
            student.left_date = date.today()
        student.save(
            update_fields=[
                'seat',
                'seat_number',
                'is_active',
                'is_deleted',
                'left_date',
                'updated_at',
            ],
        )
        student.mess.refresh_seat_counts()

    return student
