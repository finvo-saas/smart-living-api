from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from billing.models import Bill
from reports.constants import DEFAULT_BUDGET_LIMITS, MONTHS
from reports.models import Budget, ExpenseCategory


def map_description_to_category(description: str) -> tuple[str, str]:
    """Return (category_code, category_name) from bill item description."""
    desc = description.lower()
    if 'rent' in desc:
        return 'cat1', 'Rent'
    if 'electricity' in desc or 'electric' in desc:
        return 'cat2', 'Electricity'
    if 'gas' in desc:
        return 'cat3', 'Gas'
    if 'water' in desc:
        return 'cat4', 'Water'
    if 'service' in desc:
        return 'cat5', 'Service Charge'
    if 'maintenance' in desc:
        return 'cat6', 'Maintenance'
    return 'cat7', 'Other'


def _categories_by_code():
    return {c.code: c for c in ExpenseCategory.objects.all()}


def _current_period():
    now = datetime.now()
    return now.strftime('%B'), now.year


def ensure_default_budgets(user):
    """Create default budgets for user if none exist for current period."""
    month, year = _current_period()
    if Budget.objects.filter(user=user, period_month=month, period_year=year).exists():
        return

    categories = ExpenseCategory.objects.all()
    for cat in categories:
        Budget.objects.get_or_create(
            user=user,
            category=cat,
            period_month=month,
            period_year=year,
            defaults={
                'monthly_limit': Decimal(str(DEFAULT_BUDGET_LIMITS.get(cat.code, 1000))),
                'current_spending': Decimal('0'),
                'alerts': {'enabled': True, 'threshold': 80},
            },
        )


def _tenant_bills(user):
    return (
        Bill.objects.filter(tenant=user, is_deleted=False)
        .prefetch_related('items')
        .order_by('year', 'created_at')
    )


def build_monthly_expenses(user, year_filter=None):
    bills = _tenant_bills(user)
    if year_filter:
        bills = bills.filter(year=year_filter)

    grouped = defaultdict(lambda: {'total': Decimal('0'), 'categories': defaultdict(Decimal), 'bills': []})

    for bill in bills:
        key = (bill.month, bill.year)
        grouped[key]['bills'].append(str(bill.id))
        for item in bill.items.all():
            code, name = map_description_to_category(item.description)
            grouped[key]['categories'][(code, name)] += item.amount
            grouped[key]['total'] += item.amount

    result = []
    for (month, year), data in sorted(grouped.items(), key=lambda x: (x[0][1], MONTHS.index(x[0][0]))):
        total = float(data['total'])
        categories = []
        for (code, name), amount in data['categories'].items():
            amt = float(amount)
            categories.append({
                'categoryId': code,
                'categoryName': name,
                'amount': amt,
                'percentage': (amt / total * 100) if total else 0,
            })
        result.append({
            'month': month,
            'year': year,
            'total': total,
            'categories': categories,
            'bills': data['bills'],
        })
    return result


def build_yearly_expenses(monthly_expenses):
    by_year = defaultdict(list)
    for exp in monthly_expenses:
        by_year[exp['year']].append(exp)

    yearly = []
    for year, expenses in sorted(by_year.items()):
        total = sum(e['total'] for e in expenses)
        monthly_averages = [{'month': e['month'], 'average': e['total']} for e in expenses]

        cat_totals = defaultdict(lambda: {'name': '', 'total': 0.0})
        for exp in expenses:
            for cat in exp['categories']:
                cat_totals[cat['categoryId']]['name'] = cat['categoryName']
                cat_totals[cat['categoryId']]['total'] += cat['amount']

        category_totals = [
            {
                'categoryId': cid,
                'categoryName': data['name'],
                'total': data['total'],
                'percentage': (data['total'] / total * 100) if total else 0,
            }
            for cid, data in cat_totals.items()
        ]

        sorted_exp = sorted(expenses, key=lambda e: MONTHS.index(e['month']))
        trend = 'stable'
        growth_rate = 0.0
        if len(sorted_exp) >= 2:
            mid = len(sorted_exp) // 2
            first_avg = sum(e['total'] for e in sorted_exp[:mid]) / max(mid, 1)
            second_avg = sum(e['total'] for e in sorted_exp[mid:]) / max(len(sorted_exp) - mid, 1)
            growth_rate = ((second_avg - first_avg) / first_avg * 100) if first_avg else 0
            if growth_rate > 5:
                trend = 'increasing'
            elif growth_rate < -5:
                trend = 'decreasing'

        yearly.append({
            'year': year,
            'total': total,
            'monthlyAverages': monthly_averages,
            'categoryTotals': category_totals,
            'trend': trend,
            'growthRate': growth_rate,
        })
    return yearly


def build_trends(monthly_expenses):
    return [
        {
            'period': f"{e['month']} {e['year']}",
            'amount': e['total'],
            'categoryBreakdown': [
                {'categoryId': c['categoryId'], 'amount': c['amount']}
                for c in e['categories']
            ],
        }
        for e in monthly_expenses
    ]


def sync_budget_spending(user):
    """Update current_spending on budgets from current month bills."""
    month, year = _current_period()
    monthly = build_monthly_expenses(user, year_filter=year)
    current = next((m for m in monthly if m['month'] == month), None)
    if not current:
        return

    spending_by_code = {c['categoryId']: Decimal(str(c['amount'])) for c in current['categories']}
    budgets = Budget.objects.filter(user=user, period_month=month, period_year=year)
    for budget in budgets:
        code = budget.category.code
        budget.current_spending = spending_by_code.get(code, Decimal('0'))
        budget.save(update_fields=['current_spending', 'updated_at'])


def build_budgets(user):
    ensure_default_budgets(user)
    sync_budget_spending(user)
    month, year = _current_period()
    budgets = Budget.objects.filter(
        user=user,
        period_month=month,
        period_year=year,
    ).select_related('category')

    return [
        {
            'id': str(b.id),
            'categoryId': b.category.code,
            'categoryName': b.category.name,
            'monthlyLimit': float(b.monthly_limit),
            'currentSpending': float(b.current_spending),
            'period': {'month': b.period_month, 'year': b.period_year},
            'alerts': b.alerts or {'enabled': True, 'threshold': 80},
        }
        for b in budgets
    ]


def build_expense_analytics(user):
    ensure_default_budgets(user)
    sync_budget_spending(user)
    monthly = build_monthly_expenses(user)
    categories = [
        {
            'id': c.code,
            'name': c.name,
            'type': c.type,
            'color': c.color,
        }
        for c in ExpenseCategory.objects.all().order_by('code')
    ]
    return {
        'userId': str(user.id),
        'monthlyExpenses': monthly,
        'yearlyExpenses': build_yearly_expenses(monthly),
        'trends': build_trends(monthly),
        'budgets': build_budgets(user),
        'categories': categories,
    }


def generate_expense_report_data(user, start_date, end_date):
    bills = _tenant_bills(user).filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )
    total = Decimal('0')
    cat_map = defaultdict(lambda: {'name': '', 'amount': Decimal('0')})
    monthly_map = defaultdict(Decimal)
    bill_ids = []

    for bill in bills:
        bill_ids.append(str(bill.id))
        for item in bill.items.all():
            code, name = map_description_to_category(item.description)
            cat_map[code]['name'] = name
            cat_map[code]['amount'] += item.amount
            total += item.amount
            monthly_map[(bill.month, bill.year)] += item.amount

    total_f = float(total)
    return {
        'totalExpenses': total_f,
        'categoryBreakdown': [
            {
                'categoryId': code,
                'categoryName': data['name'],
                'amount': float(data['amount']),
                'percentage': (float(data['amount']) / total_f * 100) if total_f else 0,
            }
            for code, data in cat_map.items()
        ],
        'monthlyBreakdown': [
            {'month': m, 'year': y, 'amount': float(amt)}
            for (m, y), amt in sorted(monthly_map.items(), key=lambda x: (x[0][1], MONTHS.index(x[0][0])))
        ],
        'bills': bill_ids,
    }
