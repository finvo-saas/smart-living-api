"""Public meal calendar, utilities, book bridge, and মিল হিসাব API views."""
from __future__ import annotations

from datetime import date, datetime

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from mess.models import MealOffRequest, MemberDeposit, MessStudent
from mess.services import hisab
from mess.services.meal_public import apply_meal_pricing, public_meal_calendar
from mess.services.reliability import (
    electricity_profile_for,
    reliability_bundle,
    water_profile_for,
)
from mess.views import (
    _assert_mess_owner,
    _assert_mess_read,
    _get_mess,
    _is_mess_owner,
    _is_mess_student,
    _serialize_mess,
)


def _parse_date(raw, field='date') -> date:
    if not raw:
        raise InvalidError(f'{field} is required.')
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as exc:
        raise InvalidError(f'Invalid {field}.') from exc


def _get_student(mess, student_id: str) -> MessStudent:
    try:
        return MessStudent.objects.get(
            pk=student_id,
            mess=mess,
            is_deleted=False,
        )
    except MessStudent.DoesNotExist as exc:
        raise NotFoundError('Student not found.') from exc


class PublicMealCalendarView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        mess = _get_mess(pk)
        days = request.query_params.get('days') or 7
        start_raw = request.query_params.get('from')
        start = _parse_date(start_raw, 'from') if start_raw else date.today()
        try:
            days_int = int(days)
        except (TypeError, ValueError):
            days_int = 7
        return Response(api_success(public_meal_calendar(mess, days=days_int, start=start)))


class MessMealPricingView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        apply_meal_pricing(mess, request.data if isinstance(request.data, dict) else {})
        return Response(api_success(_serialize_mess(mess)))


class MessUtilitiesView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        mess = _get_mess(pk)
        return Response(api_success(reliability_bundle(mess)))

    def patch(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        data = request.data if isinstance(request.data, dict) else {}
        update_fields = []
        if 'waterProfile' in data and isinstance(data['waterProfile'], dict):
            current = water_profile_for(mess)
            current.update(data['waterProfile'])
            mess.water_profile = current
            update_fields.append('water_profile')
        if 'electricityProfile' in data and isinstance(data['electricityProfile'], dict):
            current = electricity_profile_for(mess)
            current.update(data['electricityProfile'])
            mess.electricity_profile = current
            update_fields.append('electricity_profile')
        if update_fields:
            update_fields.append('updated_at')
            mess.save(update_fields=update_fields)
        return Response(api_success(reliability_bundle(mess)))


class MessEnsureListingView(APIView):
    """Create/link public listing so seekers can book from mess detail."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        from listings.services.inventory import ensure_listing_for_mess

        listing = ensure_listing_for_mess(mess)
        mess.refresh_from_db()
        return Response(
            api_success(
                {
                    'listingId': str(listing.id),
                    'bookUrl': f'/listings/{listing.id}',
                    'mess': _serialize_mess(mess),
                }
            ),
        )


class MealGridView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        day = _parse_date(request.query_params.get('date') or date.today().isoformat())
        return Response(api_success(hisab.meal_grid(mess, day)))

    def put(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        data = request.data if isinstance(request.data, dict) else {}
        day = _parse_date(data.get('date') or date.today().isoformat())
        rows = data.get('rows') or []
        if not isinstance(rows, list):
            raise InvalidError('rows must be a list.')
        return Response(api_success(hisab.upsert_meal_grid(mess, day, rows, request.user)))


class MealGridMarkAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        data = request.data if isinstance(request.data, dict) else {}
        day = _parse_date(data.get('date') or date.today().isoformat())
        on = bool(data.get('on', True))
        return Response(api_success(hisab.mark_all_meals(mess, day, request.user, on=on)))


class MealOffListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        qs = MealOffRequest.objects.filter(mess=mess).select_related('student').order_by(
            '-created_at',
        )
        if not _is_mess_owner(mess, request.user) and request.user.role != 'admin':
            qs = qs.filter(student__user=request.user)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(
            api_success([hisab.serialize_meal_off(r) for r in qs[:100]]),
        )

    def post(self, request, pk):
        mess = _get_mess(pk)
        data = request.data if isinstance(request.data, dict) else {}
        if _is_mess_owner(mess, request.user) or request.user.role == 'admin':
            student_id = data.get('studentId')
            if not student_id:
                raise InvalidError('studentId is required.')
            student = _get_student(mess, str(student_id))
        else:
            student = MessStudent.objects.filter(
                mess=mess,
                user=request.user,
                is_active=True,
                is_deleted=False,
            ).first()
            if student is None:
                raise ForbiddenError('You are not a member of this mess.')
        req = hisab.create_meal_off(
            mess,
            student,
            {
                'start_date': _parse_date(data.get('startDate'), 'startDate'),
                'end_date': _parse_date(data.get('endDate'), 'endDate'),
                'meals': data.get('meals'),
                'reason': data.get('reason') or '',
            },
            request.user,
        )
        return Response(
            api_success(hisab.serialize_meal_off(req)),
            status=status.HTTP_201_CREATED,
        )


class MealOffReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, request_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            req = MealOffRequest.objects.get(pk=request_id, mess=mess)
        except MealOffRequest.DoesNotExist as exc:
            raise NotFoundError('Meal-off request not found.') from exc
        data = request.data if isinstance(request.data, dict) else {}
        approve = bool(data.get('approve', True))
        note = str(data.get('note') or '')
        updated = hisab.review_meal_off(req, approve=approve, user=request.user, note=note)
        return Response(api_success(hisab.serialize_meal_off(updated)))


class MemberDepositListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        qs = MemberDeposit.objects.filter(mess=mess, is_deleted=False).select_related(
            'student',
        )
        if not _is_mess_owner(mess, request.user) and request.user.role != 'admin':
            qs = qs.filter(student__user=request.user)
        return Response(
            api_success([hisab.serialize_deposit(d) for d in qs[:200]]),
        )

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        data = request.data if isinstance(request.data, dict) else {}
        student = _get_student(mess, str(data.get('studentId') or ''))
        dep = hisab.add_deposit(
            mess,
            student,
            data.get('amount'),
            _parse_date(data.get('date') or date.today().isoformat()),
            str(data.get('note') or ''),
            request.user,
            payment_method=str(
                data.get('paymentMethod') or data.get('payment_method') or 'Cash'
            ),
            transaction_id=str(
                data.get('transactionId') or data.get('transaction_id') or ''
            ),
        )
        return Response(
            api_success(hisab.serialize_deposit(dep)),
            status=status.HTTP_201_CREATED,
        )


class HisabMonthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        today = date.today()
        try:
            year = int(request.query_params.get('year') or today.year)
            month = int(request.query_params.get('month') or today.month)
        except (TypeError, ValueError) as exc:
            raise InvalidError('Invalid year/month.') from exc
        if month < 1 or month > 12:
            raise InvalidError('month must be 1–12.')
        return Response(api_success(hisab.preview_month(mess, year, month)))


class MemberMonthMealsView(APIView):
    """Day-by-day meals for one member — the owner's printable meal sheet."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, student_id):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        student = _get_student(mess, student_id)
        # Members may only pull their own sheet; owners/admins may pull anyone's.
        if not _is_mess_owner(mess, request.user) and student.user_id != request.user.id:
            raise ForbiddenError('Access denied.')

        today = date.today()
        try:
            year = int(request.query_params.get('year') or today.year)
            month = int(request.query_params.get('month') or today.month)
        except (TypeError, ValueError) as exc:
            raise InvalidError('Invalid year/month.') from exc
        if month < 1 or month > 12:
            raise InvalidError('month must be 1–12.')
        return Response(
            api_success(hisab.member_month_meals(mess, student, year, month)),
        )


class HisabCloseMonthView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        data = request.data if isinstance(request.data, dict) else {}
        today = date.today()
        try:
            year = int(data.get('year') or today.year)
            month = int(data.get('month') or today.month)
        except (TypeError, ValueError) as exc:
            raise InvalidError('Invalid year/month.') from exc
        return Response(api_success(hisab.close_month(mess, year, month, request.user)))


class HisabReopenMonthView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        data = request.data if isinstance(request.data, dict) else {}
        today = date.today()
        try:
            year = int(data.get('year') or today.year)
            month = int(data.get('month') or today.month)
        except (TypeError, ValueError) as exc:
            raise InvalidError('Invalid year/month.') from exc
        return Response(api_success(hisab.reopen_month(mess, year, month)))
