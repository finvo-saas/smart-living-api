"""Unit tests for free WhatsApp link-share helpers (no DB)."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from billing.models import PropertyKind
from billing.services.pdf import build_bill_pdf_bytes
from billing.services.public_pdf import (
    build_public_bill_pdf_url,
    pdf_file_id_from_key,
    property_slug_for_bill,
)
from billing.services.whatsapp_share import _digits_for_wa, _share_message


class WhatsAppShareHelpersTests(SimpleTestCase):
    def test_digits_normalize_bd_local(self):
        self.assertEqual(_digits_for_wa('01712345678'), '8801712345678')

    def test_digits_reject_short(self):
        self.assertEqual(_digits_for_wa('123'), '')

    def test_share_message_includes_pdf_url(self):
        bill = SimpleNamespace(
            tenant_name='Karim',
            property_name='Green Mess',
            flat_number='',
            seat_number='A1',
            month='September',
            year=2026,
            amount=5500,
            due_date=date(2026, 9, 10),
            status='pending',
        )
        msg = _share_message(bill, 'https://cdn.example/bill.pdf')
        self.assertIn('Karim', msg)
        self.assertIn('Seat A1', msg)
        self.assertIn('https://cdn.example/bill.pdf', msg)
        self.assertNotIn('wa.me', msg)

    def test_pdf_bytes_are_valid_pdf(self):
        bill = MagicMock()
        bill.id = '11111111-1111-1111-1111-111111111111'
        bill.month = 'September'
        bill.year = 2026
        bill.status = 'unpaid'
        bill.tenant_name = 'Karim'
        bill.property_name = 'Green Mess'
        bill.flat_number = ''
        bill.seat_number = 'A1'
        bill.property_type = PropertyKind.MESS
        bill.due_date = date(2026, 9, 10)
        bill.paid_date = None
        bill.amount = 5500
        bill.amount_paid = 0
        item = MagicMock()
        item.description = 'Monthly Rent'
        item.amount = 5000
        bill.items.all.return_value = [item]
        pdf = build_bill_pdf_bytes(bill)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 1500)
        self.assertIn(b'ReportLab', pdf)

    @override_settings(PUBLIC_API_URL='https://api.example.com/api/v1')
    def test_public_bill_pdf_url_includes_property_and_file(self):
        bill = SimpleNamespace(
            property_name='Green Valley Mess',
            property_id='7b5d3c6b-b127-4473-9355-ea69be9e13b7',
            pdf_key='media/bills/4caa1b87b9384215b98c1afe09fc9898.pdf',
            pdf_url='https://cdn.example/smart-living-system/media/bills/4caa1b87b9384215b98c1afe09fc9898.pdf',
        )
        self.assertEqual(property_slug_for_bill(bill), 'green-valley-mess')
        self.assertEqual(
            pdf_file_id_from_key(bill.pdf_key),
            '4caa1b87b9384215b98c1afe09fc9898',
        )
        url = build_public_bill_pdf_url(bill)
        self.assertEqual(
            url,
            'https://api.example.com/api/v1/public/bills/green-valley-mess/'
            '4caa1b87b9384215b98c1afe09fc9898.pdf',
        )
