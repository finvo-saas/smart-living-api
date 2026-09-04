"""Public meal calendar + meal system summary for seekers."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from mess.models import DailyMenu, WeeklySchedule


def _money(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _item_label(raw) -> str:
    """Normalize a menu entry (string or {name, ...}) to a display name."""
    if raw is None:
        return ''
    if isinstance(raw, str):
        text = raw.strip()
        # Legacy bad seed: Python dict repr stored/serialized as string
        if text.startswith('{') and "'name'" in text:
            import ast

            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, dict):
                    return str(parsed.get('name') or parsed.get('title') or '').strip()
            except (ValueError, SyntaxError):
                pass
        return text
    if isinstance(raw, dict):
        name = raw.get('name') or raw.get('title') or raw.get('label') or ''
        return str(name).strip()
    return str(raw).strip()


def _items(value) -> list[str]:
    if isinstance(value, list):
        labels = [_item_label(x) for x in value]
        return [label for label in labels if label]
    if isinstance(value, str) and value.strip():
        label = _item_label(value)
        return [label] if label else []
    return []


def meal_system_summary(mess) -> dict:
    return {
        'mealsPerDay': int(mess.meals_per_day or 3),
        'vegetarianOption': bool(mess.vegetarian_option),
        'mealMonthlyCharge': _money(mess.meal_monthly_charge),
        'guestMealPrice': _money(mess.guest_meal_price),
        'mealOffPolicy': mess.meal_off_policy or '',
        'fishMeatDaysPerWeek': mess.fish_meat_days_per_week,
    }


def public_meal_calendar(mess, days: int = 7, start: date | None = None) -> dict:
    """Return today + upcoming menus (and weekly schedule fallback)."""
    days = max(1, min(int(days or 7), 14))
    start = start or date.today()
    end = start + timedelta(days=days - 1)

    menus = {
        m.date: m
        for m in DailyMenu.objects.filter(mess=mess, date__gte=start, date__lte=end)
    }
    weekly = (
        WeeklySchedule.objects.filter(mess=mess, is_active=True)
        .order_by('-week_start_date')
        .first()
    )
    schedule = weekly.schedule if weekly and isinstance(weekly.schedule, dict) else {}

    weekday_keys = (
        'monday',
        'tuesday',
        'wednesday',
        'thursday',
        'friday',
        'saturday',
        'sunday',
    )

    calendar = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        menu = menus.get(day)
        if menu:
            entry = {
                'date': day.isoformat(),
                'source': 'daily',
                'breakfast': _items(menu.breakfast),
                'lunch': _items(menu.lunch),
                'dinner': _items(menu.dinner),
                'snack': _items(menu.snack),
                'notes': menu.notes or '',
            }
        else:
            day_key = weekday_keys[day.weekday()]
            day_sched = schedule.get(day_key) or schedule.get(day_key[:3]) or {}
            if not isinstance(day_sched, dict):
                day_sched = {}
            entry = {
                'date': day.isoformat(),
                'source': 'weekly' if day_sched else 'empty',
                'breakfast': _items(day_sched.get('breakfast')),
                'lunch': _items(day_sched.get('lunch')),
                'dinner': _items(day_sched.get('dinner')),
                'snack': _items(day_sched.get('snack')),
                'notes': '',
            }
        calendar.append(entry)

    today = calendar[0] if calendar and calendar[0]['date'] == date.today().isoformat() else None
    if today is None:
        for item in calendar:
            if item['date'] == date.today().isoformat():
                today = item
                break

    return {
        'messId': str(mess.id),
        'from': start.isoformat(),
        'to': end.isoformat(),
        'mealSystem': meal_system_summary(mess),
        'today': today,
        'calendar': calendar,
        'guestMealPrice': _money(mess.guest_meal_price),
    }


def apply_meal_pricing(mess, data: dict, save: bool = True) -> None:
    mapping = {
        'mealsPerDay': 'meals_per_day',
        'vegetarianOption': 'vegetarian_option',
        'mealMonthlyCharge': 'meal_monthly_charge',
        'guestMealPrice': 'guest_meal_price',
        'mealOffPolicy': 'meal_off_policy',
        'fishMeatDaysPerWeek': 'fish_meat_days_per_week',
    }
    update_fields = []
    for camel, field in mapping.items():
        if camel not in data:
            continue
        value = data[camel]
        if field in ('meal_monthly_charge', 'guest_meal_price'):
            value = None if value in (None, '',) else Decimal(str(value))
        elif field == 'meals_per_day':
            value = max(1, min(int(value or 3), 4))
        elif field == 'fish_meat_days_per_week':
            value = None if value in (None, '') else max(0, min(int(value), 7))
        elif field == 'vegetarian_option':
            value = bool(value)
        else:
            value = str(value or '')
        setattr(mess, field, value)
        update_fields.append(field)
    if save and update_fields:
        update_fields.append('updated_at')
        mess.save(update_fields=update_fields)
