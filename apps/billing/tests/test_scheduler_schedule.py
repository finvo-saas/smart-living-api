"""Unit tests for bill rule schedule math (no DB)."""

from datetime import date

from django.test import SimpleTestCase

from billing.services.scheduler import billing_period_for_run, compute_next_run


class BillRuleScheduleTests(SimpleTestCase):
    def test_monthly_next_run_without_before(self):
        # After Sep 11 → next is Oct 1
        nxt = compute_next_run(
            date(2026, 9, 11),
            {'type': 'monthly', 'dayOfMonth': 1, 'generateBeforeDays': 0},
        )
        self.assertEqual(nxt, date(2026, 10, 1))

    def test_monthly_generate_before_days(self):
        # day 1 with 2 days before → Sep cycle runs Aug 30
        nxt = compute_next_run(
            date(2026, 8, 1),
            {'type': 'monthly', 'dayOfMonth': 1, 'generateBeforeDays': 2},
        )
        self.assertEqual(nxt, date(2026, 8, 30))

    def test_billing_period_uses_scheduled_month(self):
        month, year = billing_period_for_run(
            date(2026, 8, 30),
            {'generateBeforeDays': 2},
        )
        self.assertEqual(month, 'September')
        self.assertEqual(year, 2026)

    def test_weekly_sunday(self):
        # 2026-09-11 is Friday; next Sunday run is Sep 13
        nxt = compute_next_run(
            date(2026, 9, 11),
            {'type': 'weekly', 'dayOfWeek': 0, 'generateBeforeDays': 0},
        )
        self.assertEqual(nxt, date(2026, 9, 13))
