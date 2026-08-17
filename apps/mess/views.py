from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from mess.models import (
    AttendanceRecord,
    DailyMenu,
    DEFAULT_MEAL_TIMING,
    MealPreference,
    MealTiming,
    Mess,
    MessExpense,
    MessNotice,
    MessNoticeAck,
    MessRule,
    MessStudent,
    RuleAcceptance,
    RuleViolation,
    Seat,
    SeatStatus,
    SMSGroup,
    SMSMessage,
    SMSTemplate,
    WeeklySchedule,
)
from mess.serializers import (
    AttendanceBulkSerializer,
    AttendanceMarkSerializer,
    AttendanceRecordSerializer,
    DailyMenuSerializer,
    DailyMenuWriteSerializer,
    MealPreferenceSerializer,
    MealTimingSerializer,
    MealTimingWriteSerializer,
    MessBillGetOrCreateSerializer,
    MessCreateSerializer,
    MessExpenseSerializer,
    MessExpenseWriteSerializer,
    MessRuleSerializer,
    MessRuleWriteSerializer,
    MessSerializer,
    NoticeSerializer,
    NoticeWriteSerializer,
    RuleAcceptanceSerializer,
    RuleViolationPatchSerializer,
    RuleViolationSerializer,
    RuleViolationWriteSerializer,
    SeatSerializer,
    SeatUpdateSerializer,
    SMSGroupSerializer,
    SMSGroupWriteSerializer,
    SMSMessageSerializer,
    SMSSendSerializer,
    SMSTemplateSerializer,
    SMSTemplateWriteSerializer,
    StudentAssignSerializer,
    StudentSerializer,
    WeeklyScheduleSerializer,
    WeeklyScheduleWriteSerializer,
)
from mess.services.attendance import (
    attendance_queryset,
    build_attendance_summary,
    generate_attendance_report,
    get_student_for_summary,
)
from mess.services.bills import get_or_create_mess_bill
from mess.services.expenses import generate_expense_report, monthly_expense_summary
from mess.services.seats import assign_student
from mess.services.sms import send_bulk_sms


def _mess_qs():
    return Mess.objects.filter(is_deleted=False).select_related('owner')


def _get_mess(pk):
    try:
        return _mess_qs().get(pk=pk)
    except Mess.DoesNotExist as exc:
        raise NotFoundError('Mess not found.') from exc


def _is_mess_owner(mess, user):
    return mess.owner_id == user.id or user.role == 'admin'


def _is_mess_student(mess, user):
    return MessStudent.objects.filter(
        mess=mess,
        user=user,
        is_active=True,
        is_deleted=False,
    ).exists()


def _assert_mess_owner(mess, user):
    if not _is_mess_owner(mess, user):
        raise ForbiddenError('Only the mess owner can perform this action.')


def _assert_mess_read(mess, user):
    if not user.is_authenticated:
        return
    if _is_mess_owner(mess, user) or _is_mess_student(mess, user) or user.role == 'admin':
        return
    raise ForbiddenError('You do not have access to this mess.')


def _assert_mess_manage(mess, user):
    if not user.is_authenticated:
        raise ForbiddenError('Authentication required.')
    _assert_mess_owner(mess, user)


def _serialize_mess(mess):
    return MessSerializer(mess).data


def _serialize_messes(qs):
    return MessSerializer(qs, many=True).data


def _serialize_student(student):
    return StudentSerializer(student).data


def _serialize_students(qs):
    return StudentSerializer(qs, many=True).data


def _serialize_seat(seat):
    return SeatSerializer(seat).data


def _serialize_seats(qs):
    return SeatSerializer(qs, many=True).data


def _serialize_notice(notice):
    return NoticeSerializer(notice).data


def _serialize_notices(qs):
    return NoticeSerializer(qs, many=True).data


def _get_notice(pk):
    try:
        return MessNotice.objects.select_related('mess').prefetch_related(
            'acknowledgments',
        ).get(pk=pk, is_deleted=False)
    except MessNotice.DoesNotExist as exc:
        raise NotFoundError('Notice not found.') from exc


class MessListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        qs = _mess_qs()
        city = request.query_params.get('city')
        gender = request.query_params.get('gender')
        if city:
            qs = qs.filter(city__iexact=city.strip())
        if gender and gender != 'all':
            qs = qs.filter(gender=gender)
        if request.user.is_authenticated and request.user.role == 'owner':
            owner_only = request.query_params.get('mine')
            if owner_only in ('1', 'true', 'yes'):
                qs = qs.filter(owner=request.user)
        return Response(api_success(_serialize_messes(qs)))

    def post(self, request):
        if request.user.role not in ('owner', 'admin'):
            raise ForbiddenError('Only owners can create messes.')
        serializer = MessCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mess = serializer.create_mess(request.user)
        return Response(api_success(_serialize_mess(mess)), status=status.HTTP_201_CREATED)


class MessDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        mess = _get_mess(pk)
        return Response(api_success(_serialize_mess(mess)))


class MessStudentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        if not _is_mess_owner(mess, request.user) and not _is_mess_student(mess, request.user):
            if request.user.role != 'admin':
                raise ForbiddenError('Access denied.')
        qs = MessStudent.objects.filter(mess=mess, is_deleted=False).order_by('-joined_date')
        return Response(api_success(_serialize_students(qs)))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = StudentAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student = assign_student(mess, serializer.validated_data)
        return Response(
            api_success(_serialize_student(student)),
            status=status.HTTP_201_CREATED,
        )


class MessSeatsView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        mess = _get_mess(pk)
        qs = Seat.objects.filter(mess=mess, is_deleted=False).order_by('room_number', 'seat_number')
        return Response(api_success(_serialize_seats(qs)))


class MessSeatDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, seat_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            seat = Seat.objects.get(pk=seat_id, mess=mess, is_deleted=False)
        except Seat.DoesNotExist as exc:
            raise NotFoundError('Seat not found.') from exc

        serializer = SeatUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data.get('vacate'):
            if seat.student_id:
                student = seat.student
                student.seat = None
                student.save(update_fields=['seat', 'updated_at'])
            seat.student = None
            seat.status = SeatStatus.AVAILABLE
            seat.save(update_fields=['student', 'status', 'updated_at'])
            mess.refresh_seat_counts()
        elif 'status' in data:
            seat.status = data['status']
            seat.save(update_fields=['status', 'updated_at'])
            if data['status'] == SeatStatus.AVAILABLE:
                seat.student = None
                seat.save(update_fields=['student', 'updated_at'])
            mess.refresh_seat_counts()

        return Response(api_success(_serialize_seat(seat)))


class MessNoticesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        qs = MessNotice.objects.filter(
            mess=mess,
            is_deleted=False,
        ).prefetch_related('acknowledgments').order_by('-date')
        return Response(api_success(_serialize_notices(qs)))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = NoticeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        notice = MessNotice.objects.create(
            mess=mess,
            title=data['title'],
            content=data['content'],
            date=data['date'],
            priority=data['priority'],
            category=data.get('category', 'general'),
            expiry_date=data.get('expiryDate'),
            pdf_url=data.get('pdfUrl', ''),
            image_urls=data.get('imageUrls', []),
            created_by=request.user,
        )
        return Response(
            api_success(_serialize_notice(notice)),
            status=status.HTTP_201_CREATED,
        )


class AllNoticesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'admin':
            qs = MessNotice.objects.filter(is_deleted=False)
        else:
            mess_ids = Mess.objects.filter(
                owner=request.user,
                is_deleted=False,
            ).values_list('id', flat=True)
            student_mess_ids = MessStudent.objects.filter(
                user=request.user,
                is_active=True,
                is_deleted=False,
            ).values_list('mess_id', flat=True)
            all_ids = set(mess_ids) | set(student_mess_ids)
            qs = MessNotice.objects.filter(mess_id__in=all_ids, is_deleted=False)
        qs = qs.prefetch_related('acknowledgments').order_by('-date')
        return Response(api_success(_serialize_notices(qs)))


class NoticeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notice_id):
        notice = _get_notice(notice_id)
        _assert_mess_owner(notice.mess, request.user)
        serializer = NoticeWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        field_map = {
            'title': 'title',
            'content': 'content',
            'date': 'date',
            'priority': 'priority',
            'category': 'category',
            'expiryDate': 'expiry_date',
            'pdfUrl': 'pdf_url',
            'imageUrls': 'image_urls',
        }
        for key, attr in field_map.items():
            if key in data:
                setattr(notice, attr, data[key])
        notice.save()
        return Response(api_success(_serialize_notice(notice)))

    def delete(self, request, notice_id):
        notice = _get_notice(notice_id)
        _assert_mess_owner(notice.mess, request.user)
        notice.is_deleted = True
        notice.save(update_fields=['is_deleted', 'updated_at'])
        return Response(api_success({'deleted': True}))


class NoticeAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notice_id):
        notice = _get_notice(notice_id)
        _assert_mess_read(notice.mess, request.user)
        ack, _ = MessNoticeAck.objects.get_or_create(
            notice=notice,
            user=request.user,
            defaults={'acknowledged_at': timezone.now()},
        )
        if not _:
            ack.acknowledged_at = timezone.now()
            ack.save(update_fields=['acknowledged_at', 'updated_at'])
        return Response(api_success(NoticeSerializer(notice).data))


class MessBillGetOrCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        serializer = MessBillGetOrCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data['mess'] = mess
        bill = get_or_create_mess_bill(request.user, data)
        return Response(api_success(bill))


class DailyMenuListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        qs = DailyMenu.objects.filter(mess=mess).order_by('-date')
        on_date = request.query_params.get('date')
        if on_date:
            qs = qs.filter(date=on_date)
        return Response(api_success(DailyMenuSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = DailyMenuWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        menu, created = DailyMenu.objects.update_or_create(
            mess=mess,
            date=data['date'],
            defaults={
                'breakfast': data.get('breakfast', []),
                'lunch': data.get('lunch', []),
                'dinner': data.get('dinner', []),
                'snack': data.get('snack', []),
                'notes': data.get('notes', ''),
                'created_by': request.user,
            },
        )
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(api_success(DailyMenuSerializer(menu).data), status=code)


class DailyMenuDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, menu_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            menu = DailyMenu.objects.get(pk=menu_id, mess=mess)
        except DailyMenu.DoesNotExist as exc:
            raise NotFoundError('Daily menu not found.') from exc
        serializer = DailyMenuWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for field in ('breakfast', 'lunch', 'dinner', 'snack', 'notes', 'date'):
            if field in data:
                setattr(menu, field, data[field])
        menu.save()
        return Response(api_success(DailyMenuSerializer(menu).data))


class WeeklyScheduleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        qs = WeeklySchedule.objects.filter(mess=mess).order_by('-week_start_date')
        return Response(api_success(WeeklyScheduleSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = WeeklyScheduleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        schedule = WeeklySchedule.objects.create(
            mess=mess,
            week_start_date=data['weekStartDate'],
            week_end_date=data['weekEndDate'],
            schedule=data['schedule'],
            is_active=data.get('isActive', True),
            created_by=request.user,
        )
        return Response(
            api_success(WeeklyScheduleSerializer(schedule).data),
            status=status.HTTP_201_CREATED,
        )


class WeeklyScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, schedule_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            schedule = WeeklySchedule.objects.get(pk=schedule_id, mess=mess)
        except WeeklySchedule.DoesNotExist as exc:
            raise NotFoundError('Weekly schedule not found.') from exc
        serializer = WeeklyScheduleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'weekStartDate' in data:
            schedule.week_start_date = data['weekStartDate']
        if 'weekEndDate' in data:
            schedule.week_end_date = data['weekEndDate']
        if 'schedule' in data:
            schedule.schedule = data['schedule']
        if 'isActive' in data:
            schedule.is_active = data['isActive']
        schedule.save()
        return Response(api_success(WeeklyScheduleSerializer(schedule).data))


class MealTimingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        timing, _ = MealTiming.objects.get_or_create(mess=mess)
        return Response(api_success(MealTimingSerializer(timing).data))

    def patch(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        timing, _ = MealTiming.objects.get_or_create(mess=mess)
        serializer = MealTimingWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for field in ('breakfast', 'lunch', 'dinner', 'snack'):
            if field in data:
                setattr(timing, field, data[field])
        timing.save()
        return Response(api_success(MealTimingSerializer(timing).data))


class MealPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        pref, _ = MealPreference.objects.get_or_create(
            user=request.user,
            mess=mess,
            defaults={'preferences': []},
        )
        return Response(api_success(MealPreferenceSerializer(pref).data))

    def put(self, request, pk):
        mess = _get_mess(pk)
        preferences = request.data.get('preferences', [])
        pref, _ = MealPreference.objects.update_or_create(
            user=request.user,
            mess=mess,
            defaults={'preferences': preferences},
        )
        return Response(api_success(MealPreferenceSerializer(pref).data))


class AttendanceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        start = request.query_params.get('startDate')
        end = request.query_params.get('endDate')
        on_date = request.query_params.get('date')
        student_id = request.query_params.get('studentId')

        if _is_mess_student(mess, request.user) and not _is_mess_owner(mess, request.user):
            enrollment = MessStudent.objects.filter(
                mess=mess,
                user=request.user,
                is_active=True,
            ).first()
            if enrollment:
                student_id = str(enrollment.id)

        qs = attendance_queryset(
            mess,
            start_date=date.fromisoformat(start) if start else None,
            end_date=date.fromisoformat(end) if end else None,
            on_date=date.fromisoformat(on_date) if on_date else None,
            student_id=student_id,
        )
        return Response(api_success(AttendanceRecordSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = AttendanceMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            student = MessStudent.objects.get(pk=data['studentId'], mess=mess, is_deleted=False)
        except MessStudent.DoesNotExist as exc:
            raise NotFoundError('Student not found.') from exc

        record = AttendanceRecord.objects.create(
            mess=mess,
            student=student,
            student_name=student.name,
            date=data['date'],
            status=data['status'],
            type=data.get('type', 'general'),
            check_in_time=data.get('checkInTime'),
            check_out_time=data.get('checkOutTime'),
            meal_category=data.get('mealCategory', ''),
            notes=data.get('notes', ''),
            marked_by=request.user,
            marked_at=timezone.now(),
        )
        return Response(
            api_success(AttendanceRecordSerializer(record).data),
            status=status.HTTP_201_CREATED,
        )


class AttendanceBulkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = AttendanceBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bulk_date = serializer.validated_data['date']
        created = []
        for item in serializer.validated_data['records']:
            try:
                student = MessStudent.objects.get(
                    pk=item['studentId'],
                    mess=mess,
                    is_deleted=False,
                )
            except MessStudent.DoesNotExist:
                continue
            record = AttendanceRecord.objects.create(
                mess=mess,
                student=student,
                student_name=student.name,
                date=item.get('date', bulk_date),
                status=item['status'],
                type=item.get('type', 'general'),
                check_in_time=item.get('checkInTime'),
                check_out_time=item.get('checkOutTime'),
                meal_category=item.get('mealCategory', ''),
                notes=item.get('notes', ''),
                marked_by=request.user,
                marked_at=timezone.now(),
            )
            created.append(record)
        return Response(
            api_success(AttendanceRecordSerializer(created, many=True).data),
            status=status.HTTP_201_CREATED,
        )


class AttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        student_id = request.query_params.get('studentId')
        start = request.query_params.get('startDate')
        end = request.query_params.get('endDate')
        today = timezone.now().date()
        start_date = date.fromisoformat(start) if start else today.replace(day=1)
        end_date = date.fromisoformat(end) if end else today

        if student_id:
            student = get_student_for_summary(mess, student_id)
            summary = build_attendance_summary(mess, student, start_date, end_date)
            return Response(api_success(summary))

        students = MessStudent.objects.filter(mess=mess, is_active=True, is_deleted=False)
        summaries = [
            build_attendance_summary(mess, s, start_date, end_date)
            for s in students
        ]
        return Response(api_success(summaries))


class AttendanceReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        report_type = request.data.get('reportType', 'monthly')
        start = request.data.get('startDate')
        end = request.data.get('endDate')
        report = generate_attendance_report(
            mess,
            request.user,
            report_type=report_type,
            start_date=date.fromisoformat(start) if start else None,
            end_date=date.fromisoformat(end) if end else None,
        )
        return Response(api_success(report))


class SMSTemplateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        qs = SMSTemplate.objects.filter(
            mess=mess,
            is_deleted=False,
        ).order_by('-updated_at')
        return Response(api_success(SMSTemplateSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = SMSTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        template = SMSTemplate.objects.create(
            mess=mess,
            name=data['name'],
            content=data['content'],
            variables=data.get('variables', []),
            category=data.get('category', ''),
            created_by=request.user,
        )
        return Response(
            api_success(SMSTemplateSerializer(template).data),
            status=status.HTTP_201_CREATED,
        )


class SMSTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, template_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            template = SMSTemplate.objects.get(pk=template_id, mess=mess, is_deleted=False)
        except SMSTemplate.DoesNotExist as exc:
            raise NotFoundError('SMS template not found.') from exc
        serializer = SMSTemplateWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for field in ('name', 'content', 'variables', 'category'):
            if field in data:
                setattr(template, field, data[field])
        template.save()
        return Response(api_success(SMSTemplateSerializer(template).data))

    def delete(self, request, pk, template_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            template = SMSTemplate.objects.get(pk=template_id, mess=mess, is_deleted=False)
        except SMSTemplate.DoesNotExist as exc:
            raise NotFoundError('SMS template not found.') from exc
        template.is_deleted = True
        template.save(update_fields=['is_deleted', 'updated_at'])
        return Response(api_success({'deleted': True}))


class SMSGroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        qs = SMSGroup.objects.filter(mess=mess, is_deleted=False).order_by('-updated_at')
        return Response(api_success(SMSGroupSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = SMSGroupWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        group = SMSGroup.objects.create(
            mess=mess,
            name=data['name'],
            description=data.get('description', ''),
            member_ids=data.get('memberIds', []),
            created_by=request.user,
        )
        return Response(
            api_success(SMSGroupSerializer(group).data),
            status=status.HTTP_201_CREATED,
        )


class SMSGroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, group_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            group = SMSGroup.objects.get(pk=group_id, mess=mess, is_deleted=False)
        except SMSGroup.DoesNotExist as exc:
            raise NotFoundError('SMS group not found.') from exc
        serializer = SMSGroupWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for field in ('name', 'description', 'memberIds'):
            attr = 'member_ids' if field == 'memberIds' else field
            if field in data:
                setattr(group, attr, data[field])
        group.save()
        return Response(api_success(SMSGroupSerializer(group).data))

    def delete(self, request, pk, group_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            group = SMSGroup.objects.get(pk=group_id, mess=mess, is_deleted=False)
        except SMSGroup.DoesNotExist as exc:
            raise NotFoundError('SMS group not found.') from exc
        group.is_deleted = True
        group.save(update_fields=['is_deleted', 'updated_at'])
        return Response(api_success({'deleted': True}))


class SMSMessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        qs = SMSMessage.objects.filter(mess=mess).order_by('-created_at')
        return Response(api_success(SMSMessageSerializer(qs, many=True).data))


class SMSSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = SMSSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get('templateId'):
            data['templateId'] = data['templateId']
        if data.get('groupId'):
            data['groupId'] = data['groupId']
        if data.get('studentIds'):
            data['studentIds'] = data['studentIds']
        message = send_bulk_sms(mess, request.user, data)
        return Response(
            api_success(SMSMessageSerializer(message).data),
            status=status.HTTP_201_CREATED,
        )


class SMSHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        messages = SMSMessage.objects.filter(mess=mess).order_by('-created_at')
        total_sent = sum(m.successful for m in messages)
        total_failed = sum(m.failed for m in messages)
        total_cost = sum(float(m.cost or 0) for m in messages)
        today = timezone.now().date()
        return Response(api_success({
            'messages': SMSMessageSerializer(messages, many=True).data,
            'totalSent': total_sent,
            'totalFailed': total_failed,
            'totalCost': total_cost,
            'period': {
                'startDate': (today.replace(day=1)).isoformat(),
                'endDate': today.isoformat(),
            },
        }))


class MessRuleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_read(mess, request.user)
        qs = MessRule.objects.filter(mess=mess, is_deleted=False).order_by('-created_at')
        return Response(api_success(MessRuleSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = MessRuleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        rule = MessRule.objects.create(
            mess=mess,
            title=data['title'],
            description=data['description'],
            category=data['category'],
            severity=data['severity'],
            penalty=data.get('penalty', ''),
            status=data.get('status', 'active'),
            requires_acceptance=data.get('requiresAcceptance', False),
            effective_date=data.get('effectiveDate'),
            expiry_date=data.get('expiryDate'),
            created_by=request.user,
        )
        return Response(
            api_success(MessRuleSerializer(rule).data),
            status=status.HTTP_201_CREATED,
        )


class MessRuleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, rule_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            rule = MessRule.objects.get(pk=rule_id, mess=mess, is_deleted=False)
        except MessRule.DoesNotExist as exc:
            raise NotFoundError('Rule not found.') from exc
        serializer = MessRuleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        field_map = {
            'title': 'title',
            'description': 'description',
            'category': 'category',
            'severity': 'severity',
            'penalty': 'penalty',
            'status': 'status',
            'requiresAcceptance': 'requires_acceptance',
            'effectiveDate': 'effective_date',
            'expiryDate': 'expiry_date',
        }
        for key, attr in field_map.items():
            if key in data:
                setattr(rule, attr, data[key])
        rule.save()
        return Response(api_success(MessRuleSerializer(rule).data))

    def delete(self, request, pk, rule_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            rule = MessRule.objects.get(pk=rule_id, mess=mess, is_deleted=False)
        except MessRule.DoesNotExist as exc:
            raise NotFoundError('Rule not found.') from exc
        rule.is_deleted = True
        rule.save(update_fields=['is_deleted', 'updated_at'])
        return Response(api_success({'deleted': True}))


class RuleAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, rule_id):
        mess = _get_mess(pk)
        enrollment = MessStudent.objects.filter(
            mess=mess,
            user=request.user,
            is_active=True,
            is_deleted=False,
        ).first()
        if not enrollment:
            raise ForbiddenError('Only enrolled students can accept rules.')
        try:
            rule = MessRule.objects.get(pk=rule_id, mess=mess, is_deleted=False)
        except MessRule.DoesNotExist as exc:
            raise NotFoundError('Rule not found.') from exc

        acceptance, created = RuleAcceptance.objects.get_or_create(
            rule=rule,
            student=enrollment,
            defaults={
                'accepted_at': timezone.now(),
                'accepted_by': request.user,
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:512],
            },
        )
        if not created:
            acceptance.accepted_at = timezone.now()
            acceptance.save(update_fields=['accepted_at', 'updated_at'])
        return Response(
            api_success(RuleAcceptanceSerializer(acceptance).data),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RuleViolationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        qs = RuleViolation.objects.filter(mess=mess).order_by('-violation_date')
        return Response(api_success(RuleViolationSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = RuleViolationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            rule = MessRule.objects.get(pk=data['ruleId'], mess=mess, is_deleted=False)
        except MessRule.DoesNotExist as exc:
            raise NotFoundError('Rule not found.') from exc
        try:
            student = MessStudent.objects.get(pk=data['studentId'], mess=mess, is_deleted=False)
        except MessStudent.DoesNotExist as exc:
            raise NotFoundError('Student not found.') from exc

        violation = RuleViolation.objects.create(
            rule=rule,
            student=student,
            student_name=student.name,
            mess=mess,
            violation_date=data['violationDate'],
            description=data['description'],
            severity=data['severity'],
            penalty=data.get('penalty'),
            reported_by=request.user,
            reported_at=timezone.now(),
            evidence=data.get('evidence', []),
        )
        return Response(
            api_success(RuleViolationSerializer(violation).data),
            status=status.HTTP_201_CREATED,
        )


class RuleViolationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, violation_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            violation = RuleViolation.objects.get(pk=violation_id, mess=mess)
        except RuleViolation.DoesNotExist as exc:
            raise NotFoundError('Violation not found.') from exc
        serializer = RuleViolationPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'status' in data:
            violation.status = data['status']
            if data['status'] == 'resolved':
                violation.resolved_at = timezone.now()
                violation.resolved_by = request.user
        if 'resolutionNotes' in data:
            violation.resolution_notes = data['resolutionNotes']
        violation.save()
        return Response(api_success(RuleViolationSerializer(violation).data))


class MessExpenseListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        qs = MessExpense.objects.filter(mess=mess, is_deleted=False).order_by('-date')
        return Response(api_success(MessExpenseSerializer(qs, many=True).data))

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        serializer = MessExpenseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        expense = MessExpense.objects.create(
            mess=mess,
            category=data['category'],
            description=data['description'],
            amount=data['amount'],
            date=data['date'],
            receipt_url=data.get('receiptUrl', ''),
            vendor=data.get('vendor', ''),
            notes=data.get('notes', ''),
            created_by=request.user,
        )
        return Response(
            api_success(MessExpenseSerializer(expense).data),
            status=status.HTTP_201_CREATED,
        )


class MessExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, expense_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            expense = MessExpense.objects.get(pk=expense_id, mess=mess, is_deleted=False)
        except MessExpense.DoesNotExist as exc:
            raise NotFoundError('Expense not found.') from exc
        serializer = MessExpenseWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        field_map = {
            'category': 'category',
            'description': 'description',
            'amount': 'amount',
            'date': 'date',
            'receiptUrl': 'receipt_url',
            'vendor': 'vendor',
            'notes': 'notes',
        }
        for key, attr in field_map.items():
            if key in data:
                setattr(expense, attr, data[key])
        expense.save()
        return Response(api_success(MessExpenseSerializer(expense).data))

    def delete(self, request, pk, expense_id):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        try:
            expense = MessExpense.objects.get(pk=expense_id, mess=mess, is_deleted=False)
        except MessExpense.DoesNotExist as exc:
            raise NotFoundError('Expense not found.') from exc
        expense.is_deleted = True
        expense.save(update_fields=['is_deleted', 'updated_at'])
        return Response(api_success({'deleted': True}))


class MessExpenseSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        today = timezone.now().date()
        month_num = int(month) if month else today.month
        year_num = int(year) if year else today.year
        summary = monthly_expense_summary(mess, month_num, year_num)
        return Response(api_success(summary))


class MessExpenseReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        mess = _get_mess(pk)
        _assert_mess_owner(mess, request.user)
        report_type = request.data.get('reportType', 'monthly')
        month = request.data.get('month')
        year = request.data.get('year')
        start = request.data.get('startDate')
        end = request.data.get('endDate')
        report = generate_expense_report(
            mess,
            request.user,
            report_type=report_type,
            month=int(month) if month else None,
            year=int(year) if year else None,
            start_date=date.fromisoformat(start) if start else None,
            end_date=date.fromisoformat(end) if end else None,
        )
        return Response(api_success(report))
