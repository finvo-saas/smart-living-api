from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import NotFoundError
from reports.constants import DEFAULT_REMINDER_SETTINGS
from reports.models import Budget, ExpenseCategory, ExpenseReport, Reminder, ReminderSettings, TaxDocument
from reports.serializers import (
    BudgetPatchSerializer,
    ExpenseCategorySerializer,
    ExpenseReportCreateSerializer,
    ExpenseReportSerializer,
    ReminderCreateSerializer,
    ReminderPatchSerializer,
    ReminderSerializer,
    ReminderSettingsSerializer,
    TaxDocumentCreateSerializer,
    TaxDocumentSerializer,
)
from reports.services.expenses import (
    build_budgets,
    build_expense_analytics,
    build_monthly_expenses,
    build_yearly_expenses,
    ensure_default_budgets,
    generate_expense_report_data,
)


def _get_budget(pk, user):
    try:
        return Budget.objects.select_related('category').get(pk=pk, user=user)
    except Budget.DoesNotExist as exc:
        raise NotFoundError('Budget not found.') from exc


def _get_budget_by_category(user, category_code):
    from reports.services.expenses import _current_period

    month, year = _current_period()
    ensure_default_budgets(user)
    try:
        category = ExpenseCategory.objects.get(code=category_code)
    except ExpenseCategory.DoesNotExist as exc:
        raise NotFoundError('Category not found.') from exc
    budget, _ = Budget.objects.get_or_create(
        user=user,
        category=category,
        period_month=month,
        period_year=year,
        defaults={
            'monthly_limit': 0,
            'alerts': {'enabled': True, 'threshold': 80},
        },
    )
    return budget


def _get_reminder_settings(user):
    settings, _ = ReminderSettings.objects.get_or_create(
        user=user,
        defaults={
            'rent_reminders': DEFAULT_REMINDER_SETTINGS['rentReminders'],
            'bill_reminders': DEFAULT_REMINDER_SETTINGS['billReminders'],
            'maintenance_reminders': DEFAULT_REMINDER_SETTINGS['maintenanceReminders'],
            'custom_reminders': DEFAULT_REMINDER_SETTINGS['customReminders'],
        },
    )
    return settings


class ExpenseCategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cats = ExpenseCategory.objects.all().order_by('code')
        data = ExpenseCategorySerializer([
            {'id': c.code, 'name': c.name, 'type': c.type, 'color': c.color}
            for c in cats
        ], many=True).data
        return Response(api_success(data))


class ExpenseAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(api_success(build_expense_analytics(request.user)))


class ExpenseMonthlyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = request.query_params.get('year')
        year_filter = int(year) if year else None
        data = build_monthly_expenses(request.user, year_filter=year_filter)
        return Response(api_success(data))


class ExpenseYearlyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        monthly = build_monthly_expenses(request.user)
        return Response(api_success(build_yearly_expenses(monthly)))


class ExpenseBudgetListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(api_success(build_budgets(request.user)))


class ExpenseBudgetDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        budget = _get_budget(pk, request.user)
        ser = BudgetPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if 'monthly_limit' in ser.validated_data:
            budget.monthly_limit = ser.validated_data['monthly_limit']
        if 'alerts' in ser.validated_data:
            budget.alerts = ser.validated_data['alerts']
        budget.save()
        from reports.services.expenses import build_budgets as bb

        updated = next((b for b in bb(request.user) if b['id'] == str(budget.id)), None)
        return Response(api_success(updated))


class ExpenseBudgetByCategoryView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, category_id):
        budget = _get_budget_by_category(request.user, category_id)
        ser = BudgetPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if 'monthly_limit' in ser.validated_data:
            budget.monthly_limit = ser.validated_data['monthly_limit']
        if 'alerts' in ser.validated_data:
            budget.alerts = ser.validated_data['alerts']
        budget.save()
        from reports.services.expenses import build_budgets as bb

        updated = next(
            (b for b in bb(request.user) if b['categoryId'] == category_id),
            None,
        )
        return Response(api_success(updated))


class ExpenseReportListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ExpenseReport.objects.filter(user=request.user).order_by('-created_at')
        return Response(api_success(ExpenseReportSerializer(qs, many=True).data))

    def post(self, request):
        ser = ExpenseReportCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        report_data = generate_expense_report_data(
            request.user,
            data['period_start'],
            data['period_end'],
        )
        report = ExpenseReport.objects.create(
            user=request.user,
            report_type=data.get('report_type', 'expense'),
            period_start=data['period_start'],
            period_end=data['period_end'],
            generated_by=str(request.user.id),
            data=report_data,
            format=data.get('format', 'pdf'),
            file_name=f"expense-report-{data['period_start']}-{data['period_end']}.pdf",
        )
        return Response(
            api_success(ExpenseReportSerializer(report).data),
            status=status.HTTP_201_CREATED,
        )


class TaxDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = TaxDocument.objects.filter(user=request.user).order_by('-created_at')
        return Response(api_success(TaxDocumentSerializer(qs, many=True).data))

    def post(self, request):
        ser = TaxDocumentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        report_data = generate_expense_report_data(
            request.user,
            data['period_start'],
            data['period_end'],
        )
        breakdown = [
            {
                'category': item['categoryName'],
                'amount': item['amount'],
                'description': item['categoryName'],
            }
            for item in report_data['categoryBreakdown']
        ]
        doc = TaxDocument.objects.create(
            user=request.user,
            tax_year=data['tax_year'],
            document_type=data['document_type'],
            period_start=data['period_start'],
            period_end=data['period_end'],
            total_amount=report_data['totalExpenses'],
            breakdown=breakdown,
            file_name=f"tax-{data['tax_year']}-{data['document_type']}.pdf",
        )
        return Response(
            api_success(TaxDocumentSerializer(doc).data),
            status=status.HTTP_201_CREATED,
        )


class ReminderSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings = _get_reminder_settings(request.user)
        return Response(api_success(ReminderSettingsSerializer(settings).data))

    def put(self, request):
        settings = _get_reminder_settings(request.user)
        ser = ReminderSettingsSerializer(settings, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(api_success(ser.data))


class ReminderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Reminder.objects.filter(user=request.user).order_by('-scheduled_date')
        status_filter = request.query_params.get('status')
        type_filter = request.query_params.get('type')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if type_filter:
            qs = qs.filter(type=type_filter)
        return Response(api_success(ReminderSerializer(qs, many=True).data))

    def post(self, request):
        ser = ReminderCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reminder = Reminder.objects.create(user=request.user, **ser.validated_data)
        return Response(
            api_success(ReminderSerializer(reminder).data),
            status=status.HTTP_201_CREATED,
        )


class ReminderHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Reminder.objects.filter(user=request.user)
        reminders = ReminderSerializer(qs.order_by('-scheduled_date'), many=True).data
        return Response(api_success({
            'reminders': reminders,
            'totalSent': qs.filter(status='sent').count(),
            'totalFailed': qs.filter(status='failed').count(),
            'totalPending': qs.filter(status='pending').count(),
        }))


class ReminderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            reminder = Reminder.objects.get(pk=pk, user=request.user)
        except Reminder.DoesNotExist as exc:
            raise NotFoundError('Reminder not found.') from exc

        ser = ReminderPatchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if 'status' in ser.validated_data:
            reminder.status = ser.validated_data['status']
        reminder.save()
        return Response(api_success(ReminderSerializer(reminder).data))
