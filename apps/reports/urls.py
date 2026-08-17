from django.urls import path

from reports.views import (
    ExpenseAnalyticsView,
    ExpenseBudgetByCategoryView,
    ExpenseBudgetDetailView,
    ExpenseBudgetListView,
    ExpenseCategoryListView,
    ExpenseMonthlyView,
    ExpenseReportListCreateView,
    ExpenseYearlyView,
    ReminderDetailView,
    ReminderHistoryView,
    ReminderListCreateView,
    ReminderSettingsView,
    TaxDocumentListCreateView,
)

urlpatterns = [
    path('expenses/categories/', ExpenseCategoryListView.as_view(), name='expense-categories'),
    path('expenses/analytics/', ExpenseAnalyticsView.as_view(), name='expense-analytics'),
    path('expenses/monthly/', ExpenseMonthlyView.as_view(), name='expense-monthly'),
    path('expenses/yearly/', ExpenseYearlyView.as_view(), name='expense-yearly'),
    path('expenses/budgets/', ExpenseBudgetListView.as_view(), name='expense-budgets'),
    path(
        'expenses/budgets/<uuid:pk>/',
        ExpenseBudgetDetailView.as_view(),
        name='expense-budget-detail',
    ),
    path(
        'expenses/budgets/by-category/<str:category_id>/',
        ExpenseBudgetByCategoryView.as_view(),
        name='expense-budget-by-category',
    ),
    path('reports/expense/', ExpenseReportListCreateView.as_view(), name='expense-report'),
    path('reports/tax/', TaxDocumentListCreateView.as_view(), name='tax-document'),
    path('reminders/settings/', ReminderSettingsView.as_view(), name='reminder-settings'),
    path('reminders/history/', ReminderHistoryView.as_view(), name='reminder-history'),
    path('reminders/', ReminderListCreateView.as_view(), name='reminder-list'),
    path('reminders/<uuid:pk>/', ReminderDetailView.as_view(), name='reminder-detail'),
]
