"""মিল হিসাব — BD-style meal accounting (meals, bazaar rate, deposits, month close)."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from mess.models import (
    DepositStatus,
    ExpenseCategory,
    MealOffRequest,
    MealOffStatus,
    MemberDeposit,
    MemberMealLog,
    MemberMonthBill,
    MessExpense,
    MessMonthClose,
    MessStudent,
    MonthCloseStatus,
)


TWO = Decimal('0.01')
FOUR = Decimal('0.0001')


def _d(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Decimal) -> float:
    return float(value.quantize(TWO, rounding=ROUND_HALF_UP))


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _active_students(mess):
    return list(
        MessStudent.objects.filter(mess=mess, is_active=True, is_deleted=False).order_by(
            'name',
        ),
    )


def _assert_month_open(mess, year: int, month: int):
    closed = MessMonthClose.objects.filter(
        mess=mess,
        year=year,
        month=month,
        status=MonthCloseStatus.CLOSED,
    ).exists()
    if closed:
        raise ForbiddenError('This month is already closed. Reopen to edit.')


def meal_grid(mess, day: date) -> dict:
    students = _active_students(mess)
    logs = {
        str(log.student_id): log
        for log in MemberMealLog.objects.filter(mess=mess, date=day).select_related(
            'student',
        )
    }
    rows = []
    total_meals = Decimal('0')
    total_guests = 0
    for student in students:
        log = logs.get(str(student.id))
        breakfast = _d(log.breakfast) if log else Decimal('0')
        lunch = _d(log.lunch) if log else Decimal('0')
        dinner = _d(log.dinner) if log else Decimal('0')
        gb = int(log.guest_breakfast) if log else 0
        gl = int(log.guest_lunch) if log else 0
        gd = int(log.guest_dinner) if log else 0
        member_total = breakfast + lunch + dinner
        guest_total = gb + gl + gd
        total_meals += member_total
        total_guests += guest_total
        rows.append(
            {
                'studentId': str(student.id),
                'name': student.name,
                'seatNumber': student.seat_number or '',
                'breakfast': float(breakfast),
                'lunch': float(lunch),
                'dinner': float(dinner),
                'guestBreakfast': gb,
                'guestLunch': gl,
                'guestDinner': gd,
                'memberTotal': float(member_total),
                'guestTotal': guest_total,
                'notes': log.notes if log else '',
                'logId': str(log.id) if log else None,
            },
        )
    return {
        'messId': str(mess.id),
        'date': day.isoformat(),
        'rows': rows,
        'totals': {
            'memberMeals': float(total_meals),
            'guestMeals': total_guests,
            'students': len(students),
        },
    }


@transaction.atomic
def upsert_meal_grid(mess, day: date, rows: list, user) -> dict:
    _assert_month_open(mess, day.year, day.month)
    students = {str(s.id): s for s in _active_students(mess)}
    for row in rows:
        student_id = str(row.get('studentId') or '')
        student = students.get(student_id)
        if student is None:
            continue
        breakfast = _d(row.get('breakfast', 0))
        lunch = _d(row.get('lunch', 0))
        dinner = _d(row.get('dinner', 0))
        for val in (breakfast, lunch, dinner):
            if val < 0 or val > 3:
                raise InvalidError('Meal counts must be between 0 and 3.')
        MemberMealLog.objects.update_or_create(
            mess=mess,
            student=student,
            date=day,
            defaults={
                'breakfast': breakfast,
                'lunch': lunch,
                'dinner': dinner,
                'guest_breakfast': max(0, int(row.get('guestBreakfast') or 0)),
                'guest_lunch': max(0, int(row.get('guestLunch') or 0)),
                'guest_dinner': max(0, int(row.get('guestDinner') or 0)),
                'notes': str(row.get('notes') or '')[:255],
                'marked_by': user,
            },
        )
    return meal_grid(mess, day)


def mark_all_meals(mess, day: date, user, on: bool = True) -> dict:
    value = Decimal('1') if on else Decimal('0')
    rows = [
        {
            'studentId': str(s.id),
            'breakfast': float(value),
            'lunch': float(value),
            'dinner': float(value),
            'guestBreakfast': 0,
            'guestLunch': 0,
            'guestDinner': 0,
        }
        for s in _active_students(mess)
    ]
    return upsert_meal_grid(mess, day, rows, user)


def create_meal_off(mess, student: MessStudent, data: dict, user) -> MealOffRequest:
    start = data['start_date']
    end = data['end_date']
    if end < start:
        raise InvalidError('endDate must be on or after startDate.')
    meals = data.get('meals') or {
        'breakfast': True,
        'lunch': True,
        'dinner': True,
    }
    return MealOffRequest.objects.create(
        mess=mess,
        student=student,
        start_date=start,
        end_date=end,
        meals=meals,
        reason=data.get('reason') or '',
        status=MealOffStatus.PENDING,
    )


@transaction.atomic
def review_meal_off(request_obj: MealOffRequest, approve: bool, user, note: str = '') -> MealOffRequest:
    if request_obj.status != MealOffStatus.PENDING:
        raise InvalidError('Request already reviewed.')
    request_obj.status = MealOffStatus.APPROVED if approve else MealOffStatus.REJECTED
    request_obj.reviewed_by = user
    request_obj.reviewed_at = timezone.now()
    request_obj.review_note = note or ''
    request_obj.save(
        update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'],
    )
    if approve:
        _apply_meal_off_to_logs(request_obj, user)
    return request_obj


def _apply_meal_off_to_logs(req: MealOffRequest, user) -> None:
    meals = req.meals if isinstance(req.meals, dict) else {}
    day = req.start_date
    while day <= req.end_date:
        _assert_month_open(req.mess, day.year, day.month)
        log, _ = MemberMealLog.objects.get_or_create(
            mess=req.mess,
            student=req.student,
            date=day,
            defaults={'marked_by': user},
        )
        if meals.get('breakfast', True):
            log.breakfast = Decimal('0')
        if meals.get('lunch', True):
            log.lunch = Decimal('0')
        if meals.get('dinner', True):
            log.dinner = Decimal('0')
        log.marked_by = user
        log.save()
        day = date.fromordinal(day.toordinal() + 1)


def add_deposit(
    mess,
    student: MessStudent,
    amount,
    day: date,
    note: str,
    user,
    *,
    payment_method: str = 'Cash',
    transaction_id: str = '',
    status: str | None = None,
) -> MemberDeposit:
    amount = _d(amount)
    if amount <= 0:
        raise InvalidError('Deposit amount must be positive.')
    return MemberDeposit.objects.create(
        mess=mess,
        student=student,
        amount=amount,
        date=day,
        note=note or '',
        payment_method=payment_method or 'Cash',
        transaction_id=transaction_id or '',
        status=status or DepositStatus.CONFIRMED,
        created_by=user,
        confirmed_by=user if (status or DepositStatus.CONFIRMED) == DepositStatus.CONFIRMED else None,
    )


def preview_month(mess, year: int, month: int) -> dict:
    start, end = _month_bounds(year, month)
    students = _active_students(mess)
    food_qs = MessExpense.objects.filter(
        mess=mess,
        is_deleted=False,
        date__gte=start,
        date__lte=end,
        category=ExpenseCategory.FOOD,
    )
    fixed_qs = MessExpense.objects.filter(
        mess=mess,
        is_deleted=False,
        date__gte=start,
        date__lte=end,
    ).exclude(category=ExpenseCategory.FOOD)

    bazaar_total = _d(food_qs.aggregate(t=Sum('amount'))['t'])
    fixed_total = _d(fixed_qs.aggregate(t=Sum('amount'))['t'])

    logs = MemberMealLog.objects.filter(mess=mess, date__gte=start, date__lte=end)
    total_meals = Decimal('0')
    guest_meals = 0
    per_student: dict[str, dict] = {
        str(s.id): {
            'student': s,
            'meal_count': Decimal('0'),
            'guest_meals': 0,
            'deposits': Decimal('0'),
        }
        for s in students
    }
    for log in logs:
        key = str(log.student_id)
        if key not in per_student:
            continue
        member = _d(log.breakfast) + _d(log.lunch) + _d(log.dinner)
        guests = int(log.guest_breakfast) + int(log.guest_lunch) + int(log.guest_dinner)
        per_student[key]['meal_count'] += member
        per_student[key]['guest_meals'] += guests
        total_meals += member
        guest_meals += guests

    deposits = MemberDeposit.objects.filter(
        mess=mess,
        is_deleted=False,
        status=DepositStatus.CONFIRMED,
        date__gte=start,
        date__lte=end,
    )
    for dep in deposits:
        key = str(dep.student_id)
        if key in per_student:
            per_student[key]['deposits'] += _d(dep.amount)

    meal_rate = (bazaar_total / total_meals) if total_meals > 0 else Decimal('0')
    meal_rate = meal_rate.quantize(FOUR, rounding=ROUND_HALF_UP)
    n = len(students) or 1
    fixed_share = (fixed_total / Decimal(n)).quantize(TWO, rounding=ROUND_HALF_UP)
    guest_price = _d(mess.guest_meal_price)

    members = []
    for item in per_student.values():
        meal_cost = (item['meal_count'] * meal_rate).quantize(TWO, rounding=ROUND_HALF_UP)
        guest_cost = (Decimal(item['guest_meals']) * guest_price).quantize(
            TWO,
            rounding=ROUND_HALF_UP,
        )
        total = meal_cost + guest_cost + fixed_share
        net = total - item['deposits']
        due = net if net > 0 else Decimal('0')
        credit = -net if net < 0 else Decimal('0')
        members.append(
            {
                'studentId': str(item['student'].id),
                'name': item['student'].name,
                'seatNumber': item['student'].seat_number or '',
                'mealCount': float(item['meal_count']),
                'mealCost': _money(meal_cost),
                'guestMeals': item['guest_meals'],
                'guestCost': _money(guest_cost),
                'fixedShare': _money(fixed_share),
                'deposits': _money(item['deposits']),
                'total': _money(total),
                'due': _money(due),
                'credit': _money(credit),
            },
        )

    existing = MessMonthClose.objects.filter(mess=mess, year=year, month=month).first()
    return {
        'messId': str(mess.id),
        'year': year,
        'month': month,
        'status': existing.status if existing else MonthCloseStatus.OPEN,
        'closedAt': existing.closed_at.isoformat() if existing and existing.closed_at else None,
        'bazaarTotal': _money(bazaar_total),
        'fixedTotal': _money(fixed_total),
        'totalMeals': float(total_meals),
        'mealRate': float(meal_rate),
        'guestMealPrice': _money(guest_price) if mess.guest_meal_price is not None else None,
        'guestMeals': guest_meals,
        'activeStudents': len(students),
        'fixedShare': _money(fixed_share),
        'members': members,
        'note': (
            'Meal rate = bazaar (food) expenses ÷ total member meals. '
            'Non-food expenses split equally. Guest meals use guest meal price.'
        ),
        # Live bKash/Nagad settlement intentionally not wired — keep as product TODO (M1).
        'paymentTodo': True,
    }


def member_month_meals(mess, student, year: int, month: int) -> dict:
    """One member's day-by-day meals for a month — the printable মিল হিসাব sheet.

    Costs mirror preview_month so the sheet and the month rollup never disagree.
    Reads by student rather than the active roster, so a member who moved out
    mid-month still gets the days they were served.
    """
    start, end = _month_bounds(year, month)
    logs = {
        log.date: log
        for log in MemberMealLog.objects.filter(
            mess=mess,
            student=student,
            date__gte=start,
            date__lte=end,
        )
    }

    summary = preview_month(mess, year, month)
    row = next(
        (r for r in summary['members'] if r['studentId'] == str(student.id)),
        None,
    )
    meal_rate = _d(summary['mealRate'])
    guest_price = _d(mess.guest_meal_price)

    days = []
    breakfast_total = Decimal('0')
    lunch_total = Decimal('0')
    dinner_total = Decimal('0')
    guest_total = 0
    days_with_meals = 0

    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        log = logs.get(day)
        breakfast = _d(log.breakfast) if log else Decimal('0')
        lunch = _d(log.lunch) if log else Decimal('0')
        dinner = _d(log.dinner) if log else Decimal('0')
        gb = int(log.guest_breakfast) if log else 0
        gl = int(log.guest_lunch) if log else 0
        gd = int(log.guest_dinner) if log else 0
        member_total = breakfast + lunch + dinner
        guests = gb + gl + gd

        breakfast_total += breakfast
        lunch_total += lunch
        dinner_total += dinner
        guest_total += guests
        if member_total > 0 or guests > 0:
            days_with_meals += 1

        days.append(
            {
                'date': day.isoformat(),
                'day': day.day,
                'weekday': day.strftime('%a'),
                'breakfast': float(breakfast),
                'lunch': float(lunch),
                'dinner': float(dinner),
                'guestBreakfast': gb,
                'guestLunch': gl,
                'guestDinner': gd,
                'memberTotal': float(member_total),
                'guestTotal': guests,
                'notes': log.notes if log else '',
                'logged': log is not None,
            },
        )

    meal_count = breakfast_total + lunch_total + dinner_total
    meal_cost = (meal_count * meal_rate).quantize(TWO, rounding=ROUND_HALF_UP)
    guest_cost = (Decimal(guest_total) * guest_price).quantize(
        TWO,
        rounding=ROUND_HALF_UP,
    )
    fixed_share = _d(row['fixedShare']) if row else Decimal('0')
    deposits = _d(
        MemberDeposit.objects.filter(
            mess=mess,
            student=student,
            is_deleted=False,
            status=DepositStatus.CONFIRMED,
            date__gte=start,
            date__lte=end,
        ).aggregate(t=Sum('amount'))['t'],
    )
    total = meal_cost + guest_cost + fixed_share
    net = total - deposits

    return {
        'messId': str(mess.id),
        'messName': mess.name,
        'year': year,
        'month': month,
        'monthStart': start.isoformat(),
        'monthEnd': end.isoformat(),
        'status': summary['status'],
        'member': {
            'studentId': str(student.id),
            'name': student.name,
            'phone': student.phone,
            'seatNumber': student.seat_number or '',
            'occupantType': student.occupant_type,
            'isActive': student.is_active,
        },
        'days': days,
        'totals': {
            'breakfast': float(breakfast_total),
            'lunch': float(lunch_total),
            'dinner': float(dinner_total),
            'memberMeals': float(meal_count),
            'guestMeals': guest_total,
            'daysWithMeals': days_with_meals,
            'daysInMonth': len(days),
        },
        'costs': {
            'mealRate': float(meal_rate),
            'mealCost': _money(meal_cost),
            'guestMealPrice': (
                _money(guest_price) if mess.guest_meal_price is not None else None
            ),
            'guestCost': _money(guest_cost),
            'fixedShare': _money(fixed_share),
            'deposits': _money(deposits),
            'total': _money(total),
            'due': _money(net if net > 0 else Decimal('0')),
            'credit': _money(-net if net < 0 else Decimal('0')),
        },
        'generatedAt': timezone.now().isoformat(),
    }


@transaction.atomic
def close_month(mess, year: int, month: int, user) -> dict:
    existing = MessMonthClose.objects.filter(mess=mess, year=year, month=month).first()
    if existing and existing.status == MonthCloseStatus.CLOSED:
        raise InvalidError('Month already closed.')

    preview = preview_month(mess, year, month)
    close_obj, _ = MessMonthClose.objects.update_or_create(
        mess=mess,
        year=year,
        month=month,
        defaults={
            'status': MonthCloseStatus.CLOSED,
            'bazaar_total': _d(preview['bazaarTotal']),
            'fixed_total': _d(preview['fixedTotal']),
            'total_meals': _d(preview['totalMeals']),
            'meal_rate': _d(preview['mealRate']),
            'guest_meal_total': _d(preview['guestMeals']),
            'closed_at': timezone.now(),
            'closed_by': user,
            'snapshot': preview,
        },
    )
    close_obj.member_bills.all().delete()
    students = {str(s.id): s for s in _active_students(mess)}
    for row in preview['members']:
        student = students.get(row['studentId'])
        if student is None:
            continue
        MemberMonthBill.objects.create(
            month_close=close_obj,
            student=student,
            student_name=student.name,
            meal_count=_d(row['mealCount']),
            meal_cost=_d(row['mealCost']),
            guest_meals=int(row['guestMeals']),
            guest_cost=_d(row['guestCost']),
            fixed_share=_d(row['fixedShare']),
            deposits=_d(row['deposits']),
            total=_d(row['total']),
            due=_d(row['due']),
            credit=_d(row['credit']),
        )
    from mess.notify import schedule_hisab_closed

    schedule_hisab_closed(mess.id, year, month)
    return preview_month(mess, year, month)


@transaction.atomic
def reopen_month(mess, year: int, month: int) -> dict:
    close_obj = MessMonthClose.objects.filter(mess=mess, year=year, month=month).first()
    if close_obj is None:
        raise NotFoundError('No closed month found.')
    close_obj.status = MonthCloseStatus.OPEN
    close_obj.closed_at = None
    close_obj.closed_by = None
    close_obj.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at'])
    close_obj.member_bills.all().delete()
    return preview_month(mess, year, month)


def serialize_meal_off(req: MealOffRequest) -> dict:
    return {
        'id': str(req.id),
        'messId': str(req.mess_id),
        'studentId': str(req.student_id),
        'studentName': req.student.name if req.student_id else '',
        'startDate': req.start_date.isoformat(),
        'endDate': req.end_date.isoformat(),
        'meals': req.meals or {},
        'reason': req.reason,
        'status': req.status,
        'reviewNote': req.review_note,
        'reviewedAt': req.reviewed_at.isoformat() if req.reviewed_at else None,
        'createdAt': req.created_at.isoformat() if req.created_at else None,
    }


def serialize_deposit(dep: MemberDeposit) -> dict:
    return {
        'id': str(dep.id),
        'messId': str(dep.mess_id),
        'studentId': str(dep.student_id),
        'studentName': dep.student.name if dep.student_id else '',
        'amount': _money(_d(dep.amount)),
        'date': dep.date.isoformat(),
        'note': dep.note,
        'paymentMethod': dep.payment_method or 'Cash',
        'transactionId': dep.transaction_id or '',
        'status': dep.status,
        'createdAt': dep.created_at.isoformat() if dep.created_at else None,
    }
