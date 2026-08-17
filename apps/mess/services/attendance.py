"""Attendance summaries and report generation."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from core.exceptions import NotFoundError
from mess.models import AttendanceRecord, AttendanceStatus, Mess, MessStudent


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def attendance_queryset(mess: Mess, *, start_date=None, end_date=None, on_date=None, student_id=None):
    qs = AttendanceRecord.objects.filter(mess=mess).select_related('student')
    if on_date:
        qs = qs.filter(date=on_date)
    else:
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
    if student_id:
        qs = qs.filter(student_id=student_id)
    return qs.order_by('-date', '-marked_at')


def build_attendance_summary(
    mess: Mess,
    student: MessStudent,
    start_date: date,
    end_date: date,
) -> dict:
    records = AttendanceRecord.objects.filter(
        mess=mess,
        student=student,
        date__gte=start_date,
        date__lte=end_date,
    )
    total_days = (end_date - start_date).days + 1
    present = records.filter(status=AttendanceStatus.PRESENT).count()
    absent = records.filter(status=AttendanceStatus.ABSENT).count()
    late = records.filter(status=AttendanceStatus.LATE).count()
    excused = records.filter(status=AttendanceStatus.EXCUSED).count()
    meal_attended = records.filter(status=AttendanceStatus.MEAL_ATTENDED).count()
    meal_absent = records.filter(status=AttendanceStatus.MEAL_ABSENT).count()

    attendance_rate = round((present / total_days) * 100, 1) if total_days else 0
    meal_total = meal_attended + meal_absent
    meal_rate = round((meal_attended / meal_total) * 100, 1) if meal_total else 0

    return {
        'studentId': str(student.id),
        'studentName': student.name,
        'messId': str(mess.id),
        'period': {
            'startDate': start_date.isoformat(),
            'endDate': end_date.isoformat(),
        },
        'totalDays': total_days,
        'presentDays': present,
        'absentDays': absent,
        'lateDays': late,
        'excusedDays': excused,
        'mealAttended': meal_attended,
        'mealAbsent': meal_absent,
        'attendanceRate': attendance_rate,
        'mealAttendanceRate': meal_rate,
    }


def generate_attendance_report(
    mess: Mess,
    user,
    *,
    report_type: str = 'monthly',
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    today = timezone.now().date()
    if not end_date:
        end_date = today
    if not start_date:
        if report_type == 'daily':
            start_date = today
        elif report_type == 'weekly':
            start_date = today - timedelta(days=6)
        elif report_type == 'monthly':
            start_date = today.replace(day=1)
        else:
            start_date = today - timedelta(days=30)

    students = MessStudent.objects.filter(
        mess=mess,
        is_active=True,
        is_deleted=False,
    )
    summaries = [
        build_attendance_summary(mess, student, start_date, end_date)
        for student in students
    ]

    total_present = sum(s['presentDays'] for s in summaries)
    total_absent = sum(s['absentDays'] for s in summaries)
    total_late = sum(s['lateDays'] for s in summaries)
    avg_rate = (
        round(sum(s['attendanceRate'] for s in summaries) / len(summaries), 1)
        if summaries
        else 0
    )

    return {
        'id': str(uuid.uuid4()),
        'messId': str(mess.id),
        'reportType': report_type,
        'period': {
            'startDate': start_date.isoformat(),
            'endDate': end_date.isoformat(),
        },
        'generatedAt': timezone.now().isoformat(),
        'generatedBy': str(user.id),
        'summary': {
            'totalStudents': len(summaries),
            'averageAttendanceRate': avg_rate,
            'totalPresentDays': total_present,
            'totalAbsentDays': total_absent,
            'totalLateDays': total_late,
        },
        'studentSummaries': summaries,
    }


def get_student_for_summary(mess: Mess, student_id: str) -> MessStudent:
    try:
        return MessStudent.objects.get(
            pk=student_id,
            mess=mess,
            is_deleted=False,
        )
    except MessStudent.DoesNotExist as exc:
        raise NotFoundError('Student not found.') from exc
