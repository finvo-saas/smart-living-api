"""Expense summaries and report generation."""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date

from django.db.models import Sum
from django.utils import timezone

from mess.models import ExpenseCategory, Mess, MessExpense


def monthly_expense_summary(mess: Mess, month: int, year: int) -> dict:
    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December',
    }
    month_name = month_names.get(month, 'January')
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])

    expenses = MessExpense.objects.filter(
        mess=mess,
        date__gte=start,
        date__lte=end,
        is_deleted=False,
    )
    total = expenses.aggregate(total=Sum('amount'))['total'] or 0
    total_float = float(total)
    expense_count = expenses.count()
    days_in_month = monthrange(year, month)[1]
    avg_daily = round(total_float / days_in_month, 2) if days_in_month else 0

    category_totals = {}
    for row in expenses.values('category').annotate(amount=Sum('amount')):
        category_totals[row['category']] = float(row['amount'] or 0)

    breakdown = []
    for cat in ExpenseCategory.values:
        amount = category_totals.get(cat, 0)
        pct = round((amount / total_float) * 100, 1) if total_float else 0
        breakdown.append({
            'category': cat,
            'amount': amount,
            'percentage': pct,
        })

    return {
        'messId': str(mess.id),
        'month': month_name,
        'year': year,
        'totalAmount': total_float,
        'categoryBreakdown': breakdown,
        'expenseCount': expense_count,
        'averageDailyExpense': avg_daily,
    }


def auto_split_expenses(mess: Mess, month: int | None = None, year: int | None = None) -> dict:
    """Split utility-style expenses equally across active mess students."""
    today = timezone.now().date()
    month = month or today.month
    year = year or today.year
    summary = monthly_expense_summary(mess, month, year)

    from mess.models import MessStudent

    students = list(
        MessStudent.objects.filter(mess=mess, is_active=True, is_deleted=False)
        .order_by('name')
    )
    headcount = max(len(students), 1)

    # Prefer utilities-like categories for shared bills; fall back to all.
    util_keys = {'utilities', 'food', 'supplies'}
    util_total = sum(
        row['amount']
        for row in summary['categoryBreakdown']
        if row['category'] in util_keys
    )
    split_total = util_total if util_total > 0 else float(summary['totalAmount'] or 0)
    per_person = round(split_total / headcount, 2)

    shares = []
    for student in students:
        shares.append({
            'studentId': str(student.id),
            'name': student.name,
            'seatNumber': student.seat_number or '',
            'share': per_person,
        })
    if not shares:
        shares.append({
            'studentId': None,
            'name': 'Unassigned seat pool',
            'seatNumber': '',
            'share': per_person,
        })

    by_category = []
    for row in summary['categoryBreakdown']:
        if row['amount'] <= 0:
            continue
        by_category.append({
            'category': row['category'],
            'total': row['amount'],
            'perPerson': round(row['amount'] / headcount, 2),
        })

    return {
        'messId': str(mess.id),
        'month': summary['month'],
        'year': year,
        'activeStudents': len(students),
        'splitTotal': split_total,
        'perPerson': per_person,
        'shares': shares,
        'byCategory': by_category,
        'note': 'Equal split across active students for the selected month.',
    }


def generate_expense_report(
    mess: Mess,
    user,
    *,
    report_type: str = 'monthly',
    month: int | None = None,
    year: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    today = timezone.now().date()
    if report_type == 'monthly':
        month = month or today.month
        year = year or today.year
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        summary = monthly_expense_summary(mess, month, year)
    elif report_type == 'yearly':
        year = year or today.year
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        summary = {
            'messId': str(mess.id),
            'month': 'Year',
            'year': year,
            'totalAmount': 0,
            'categoryBreakdown': [],
            'expenseCount': 0,
            'averageDailyExpense': 0,
        }
        expenses_qs = MessExpense.objects.filter(
            mess=mess,
            date__gte=start,
            date__lte=end,
            is_deleted=False,
        )
        total = float(expenses_qs.aggregate(t=Sum('amount'))['t'] or 0)
        summary['totalAmount'] = total
        summary['expenseCount'] = expenses_qs.count()
        summary['averageDailyExpense'] = round(total / 365, 2) if total else 0
    else:
        start = start_date or today.replace(day=1)
        end = end_date or today
        expenses_qs = MessExpense.objects.filter(
            mess=mess,
            date__gte=start,
            date__lte=end,
            is_deleted=False,
        )
        total = float(expenses_qs.aggregate(t=Sum('amount'))['t'] or 0)
        summary = {
            'messId': str(mess.id),
            'month': 'Custom',
            'year': start.year,
            'totalAmount': total,
            'categoryBreakdown': [],
            'expenseCount': expenses_qs.count(),
            'averageDailyExpense': round(total / max((end - start).days + 1, 1), 2),
        }

    expenses_qs = MessExpense.objects.filter(
        mess=mess,
        date__gte=start,
        date__lte=end,
        is_deleted=False,
    )
    expense_ids = [str(eid) for eid in expenses_qs.values_list('id', flat=True)]

    return {
        'id': str(uuid.uuid4()),
        'messId': str(mess.id),
        'reportType': report_type,
        'period': {
            'startDate': start.isoformat(),
            'endDate': end.isoformat(),
        },
        'generatedAt': timezone.now().isoformat(),
        'generatedBy': str(user.id),
        'summary': summary,
        'expenses': expense_ids,
    }
