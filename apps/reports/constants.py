"""Fixed expense categories matching frontend mockExpenses."""

EXPENSE_CATEGORY_SEED = [
    {'code': 'cat1', 'name': 'Rent', 'type': 'rent', 'color': '#3b82f6'},
    {'code': 'cat2', 'name': 'Electricity', 'type': 'utilities', 'color': '#f59e0b'},
    {'code': 'cat3', 'name': 'Gas', 'type': 'utilities', 'color': '#ef4444'},
    {'code': 'cat4', 'name': 'Water', 'type': 'utilities', 'color': '#06b6d4'},
    {'code': 'cat5', 'name': 'Service Charge', 'type': 'service', 'color': '#8b5cf6'},
    {'code': 'cat6', 'name': 'Maintenance', 'type': 'maintenance', 'color': '#ec4899'},
    {'code': 'cat7', 'name': 'Other', 'type': 'other', 'color': '#6b7280'},
]

MONTHS = [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
]

DEFAULT_BUDGET_LIMITS = {
    'cat1': 15000,
    'cat2': 3000,
    'cat3': 2000,
    'cat4': 1500,
    'cat5': 2000,
    'cat6': 1000,
    'cat7': 500,
}

DEFAULT_REMINDER_SETTINGS = {
    'rentReminders': {
        'enabled': True,
        'daysBefore': [7, 3, 1],
        'channels': ['sms', 'push', 'email'],
        'time': '09:00',
    },
    'billReminders': {
        'enabled': True,
        'daysBefore': [5, 2],
        'channels': ['push', 'email'],
        'time': '10:00',
    },
    'maintenanceReminders': {
        'enabled': True,
        'channels': ['push'],
    },
    'customReminders': {
        'enabled': True,
        'defaultChannels': ['push', 'email'],
    },
}
