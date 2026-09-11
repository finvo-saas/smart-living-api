"""Automated bill generation from BillGenerationRule schedules."""

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from billing.models import BillGenerationRule, BillTemplate, MeterReading, PropertyKind
from billing.services.generation import (
    MONTH_NAMES,
    generate_bill_for_flat,
    generate_bill_for_mess_member,
)
from mess.models import Mess, MessStudent
from portfolio.models import Building, Flat

logger = logging.getLogger(__name__)

# Avoid runaway catch-up if beat was down for a long time.
MAX_CATCHUP_CYCLES = 3


def _js_weekday(d: date) -> int:
    """Match frontend dayOfWeek: Sunday=0 … Saturday=6."""
    return (d.weekday() + 1) % 7


def _schedule_dict(rule: BillGenerationRule) -> dict:
    return rule.schedule if isinstance(rule.schedule, dict) else {}


def billing_period_for_run(run_date: date, schedule: dict) -> tuple[str, int]:
    """
    Bills are for the month of the *scheduled* date.

    run_date = scheduled_date - generateBeforeDays, so scheduled_date = run_date + before.
    Example: dayOfMonth=1, before=2 → run Dec 30 → billing month January.
    """
    before = int(schedule.get('generateBeforeDays') or 0)
    scheduled = run_date + timedelta(days=max(0, before))
    return MONTH_NAMES[scheduled.month], scheduled.year


def compute_next_run(after: date, schedule: dict | None) -> date | None:
    """
    First run date strictly after `after`.

    Searches forward so weekly/custom/monthly all share one API.
    """
    schedule = schedule or {}
    start = after + timedelta(days=1)
    stype = schedule.get('type') or 'monthly'
    before = max(0, int(schedule.get('generateBeforeDays') or 0))

    if stype == 'weekly':
        target = int(schedule.get('dayOfWeek') or 0)
        d = start
        for _ in range(21 + before):
            scheduled = d + timedelta(days=before)
            if _js_weekday(scheduled) == target:
                return d
            d += timedelta(days=1)
        return None

    if stype == 'custom':
        days = [
            int(x)
            for x in (schedule.get('customDays') or [])
            if str(x).isdigit() or isinstance(x, int)
        ]
        days = sorted({d for d in days if 1 <= d <= 31})
        if not days:
            days = [1]
        y, m = start.year, start.month
        for _ in range(24):
            last = monthrange(y, m)[1]
            for day in days:
                scheduled = date(y, m, min(day, last))
                run = scheduled - timedelta(days=before)
                if run >= start:
                    return run
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
        return None

    # monthly (default)
    day = int(schedule.get('dayOfMonth') or 1)
    day = min(max(day, 1), 31)
    y, m = start.year, start.month
    for _ in range(24):
        last = monthrange(y, m)[1]
        scheduled = date(y, m, min(day, last))
        run = scheduled - timedelta(days=before)
        if run >= start:
            return run
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return None


def resolve_rule_targets(
    rule: BillGenerationRule,
) -> tuple[list[Building], list[Mess]]:
    """Buildings and messes this rule should generate bills for."""
    owner = rule.owner
    template = rule.template
    ptype = (rule.property_type or getattr(template, 'property_type', '') or '').strip()
    pid = rule.property_id or getattr(template, 'property_id', None)

    buildings_qs = Building.objects.filter(owner=owner)
    messes_qs = Mess.objects.filter(owner=owner)

    if pid:
        return (
            list(buildings_qs.filter(pk=pid)),
            list(messes_qs.filter(pk=pid)),
        )

    if ptype == PropertyKind.APARTMENT:
        return list(buildings_qs), []
    if ptype == PropertyKind.MESS:
        return [], list(messes_qs)
    return list(buildings_qs), list(messes_qs)


def _due_day(schedule: dict) -> int:
    raw = schedule.get('dueDateDay')
    try:
        day = int(raw if raw is not None else 5)
    except (TypeError, ValueError):
        day = 5
    return min(max(day, 1), 31)


@transaction.atomic
def _generate_for_buildings(
    *,
    owner,
    buildings: list[Building],
    template: BillTemplate | None,
    month: str,
    year: int,
    due_day: int,
) -> int:
    created = 0
    flat_filter_id = getattr(template, 'flat_id', None) if template else None
    for building in buildings:
        flats = (
            Flat.objects.filter(building=building)
            .select_related('building')
            .prefetch_related('tenancies')
        )
        if flat_filter_id:
            flats = flats.filter(pk=flat_filter_id)
        for flat in flats:
            meter = MeterReading.objects.filter(
                owner=owner,
                property_id=building.id,
                flat=flat,
                month=month,
                year=year,
            ).first()
            bill = generate_bill_for_flat(
                owner,
                building=building,
                flat=flat,
                month=month,
                year=year,
                template=template,
                meter_reading=meter,
                due_day=due_day,
                occupied_only=True,
            )
            if bill:
                created += 1
    return created


@transaction.atomic
def _generate_for_messes(
    *,
    owner,
    messes: list[Mess],
    template: BillTemplate | None,
    month: str,
    year: int,
    due_day: int,
) -> int:
    created = 0
    for mess in messes:
        students = MessStudent.objects.filter(
            mess=mess,
            is_active=True,
            is_deleted=False,
            left_date__isnull=True,
        ).select_related('user', 'mess')
        meter = MeterReading.objects.filter(
            owner=owner,
            property_id=mess.id,
            month=month,
            year=year,
            flat__isnull=True,
        ).first()
        for student in students:
            bill = generate_bill_for_mess_member(
                owner,
                mess=mess,
                student=student,
                month=month,
                year=year,
                template=template,
                meter_reading=meter,
                due_day=due_day,
            )
            if bill:
                created += 1
    return created


def run_single_rule(
    rule: BillGenerationRule,
    *,
    today: date | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Run catch-up cycles for one rule while next_run <= today.

    Returns a summary dict for logging / Celery results.
    """
    today = today or timezone.localdate()
    schedule = _schedule_dict(rule)
    summary = {
        'ruleId': str(rule.id),
        'ruleName': rule.name,
        'cycles': 0,
        'billsCreated': 0,
        'skipped': False,
        'reason': '',
    }

    if not rule.is_active:
        summary['skipped'] = True
        summary['reason'] = 'inactive'
        return summary

    template = (
        BillTemplate.objects.prefetch_related('items')
        .filter(pk=rule.template_id, owner=rule.owner, is_active=True)
        .first()
    )
    if not template:
        summary['skipped'] = True
        summary['reason'] = 'template_missing_or_inactive'
        logger.warning('Rule %s skipped: template missing/inactive', rule.id)
        # Still advance next_run so we do not retry forever every hour.
        if not dry_run:
            nxt = compute_next_run(today, schedule)
            BillGenerationRule.objects.filter(pk=rule.pk).update(
                next_run=nxt,
                updated_at=timezone.now(),
            )
        return summary

    if rule.next_run is None:
        nxt = compute_next_run(today - timedelta(days=1), schedule)
        if dry_run:
            summary['reason'] = f'would_set_next_run={nxt}'
            return summary
        rule.next_run = nxt
        rule.save(update_fields=['next_run', 'updated_at'])

    if rule.next_run is None or rule.next_run > today:
        summary['skipped'] = True
        summary['reason'] = 'not_due'
        return summary

    buildings, messes = resolve_rule_targets(rule)
    due_day = _due_day(schedule)
    cycles = 0
    bills = 0
    cursor = rule.next_run

    while cursor is not None and cursor <= today and cycles < MAX_CATCHUP_CYCLES:
        month, year = billing_period_for_run(cursor, schedule)
        if dry_run:
            summary['cycles'] = cycles + 1
            summary['reason'] = f'would_generate {month} {year}'
            break

        created_b = _generate_for_buildings(
            owner=rule.owner,
            buildings=buildings,
            template=template,
            month=month,
            year=year,
            due_day=due_day,
        )
        created_m = _generate_for_messes(
            owner=rule.owner,
            messes=messes,
            template=template,
            month=month,
            year=year,
            due_day=due_day,
        )
        bills += created_b + created_m
        cycles += 1
        cursor = compute_next_run(cursor, schedule)

    if not dry_run and cycles > 0:
        BillGenerationRule.objects.filter(pk=rule.pk).update(
            last_run=today,
            next_run=cursor,
            updated_at=timezone.now(),
        )

    summary['cycles'] = cycles
    summary['billsCreated'] = bills
    summary['nextRun'] = cursor.isoformat() if cursor else None
    return summary


def run_due_bill_rules(
    *,
    today: date | None = None,
    dry_run: bool = False,
    rule_id: str | None = None,
) -> dict:
    """Entry point for Celery / management command."""
    today = today or timezone.localdate()
    qs = (
        BillGenerationRule.objects.filter(is_active=True)
        .select_related('owner', 'template')
        .order_by('next_run', 'created_at')
    )
    if rule_id:
        qs = qs.filter(pk=rule_id)

    results = []
    total_bills = 0
    for rule in qs:
        # Include rules with null next_run (needs backfill) or due.
        if rule.next_run is not None and rule.next_run > today:
            continue
        try:
            result = run_single_rule(rule, today=today, dry_run=dry_run)
        except Exception:  # noqa: BLE001 — isolate per-rule failures
            logger.exception('Bill rule %s failed', rule.id)
            result = {
                'ruleId': str(rule.id),
                'ruleName': rule.name,
                'cycles': 0,
                'billsCreated': 0,
                'skipped': True,
                'reason': 'error',
            }
        results.append(result)
        total_bills += int(result.get('billsCreated') or 0)

    return {
        'asOf': today.isoformat(),
        'dryRun': dry_run,
        'rulesProcessed': len(results),
        'billsCreated': total_bills,
        'results': results,
    }
