"""Professional bill / rent invoice PDF (reportlab).

Uses Helvetica (built-in) so output stays portable; non-Latin glyphs are
replaced safely. Template version is embedded in the stored filename so
WhatsApp share regenerates when the layout changes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from billing.models import Bill

# Bump when layout changes — ensure_bill_pdf regenerates older stored PDFs.
PDF_TEMPLATE_VERSION = 'v2'

# Calm professional palette (slate + teal accent — not purple/cream AI defaults).
COLOR_INK = HexColor('#0F172A')
COLOR_MUTED = HexColor('#64748B')
COLOR_LINE = HexColor('#E2E8F0')
COLOR_HEADER = HexColor('#0F766E')
COLOR_HEADER_SOFT = HexColor('#CCFBF1')
COLOR_ROW_ALT = HexColor('#F8FAFC')
COLOR_TOTAL_BG = HexColor('#F1F5F9')
COLOR_PAID = HexColor('#15803D')
COLOR_UNPAID = HexColor('#B45309')
COLOR_OVERDUE = HexColor('#B91C1C')


def _safe(text) -> str:
    """Keep PDF text renderable with Helvetica (Latin-1)."""
    if text is None:
        return ''
    raw = str(text).replace('\u09f3', 'BDT ').replace('৳', 'BDT ')
    return raw.encode('latin-1', 'replace').decode('latin-1')


def _money(amount) -> str:
    try:
        if isinstance(amount, Decimal):
            value = float(amount)
        else:
            value = float(amount)
    except (TypeError, ValueError, InvalidOperation):
        value = 0.0
    return f'BDT {value:,.2f}'


def _unit_label(bill: Bill) -> str:
    if bill.flat_number:
        return f'Flat {bill.flat_number}'
    if bill.seat_number:
        return f'Seat {bill.seat_number}'
    return '-'


def _property_type_label(raw: str | None) -> str:
    mapping = {
        'mess': 'Mess / Hostel',
        'apartment': 'Apartment',
        'hotel': 'Hotel',
        'hostel': 'Hostel',
    }
    key = (raw or '').strip().lower()
    return mapping.get(key, (raw or '-').replace('_', ' ').title() or '-')


def _status_style(status: str | None) -> tuple[str, Color]:
    key = (status or '').strip().lower()
    if key == 'paid':
        return 'PAID', COLOR_PAID
    if key == 'overdue':
        return 'OVERDUE', COLOR_OVERDUE
    if key in ('unpaid', 'pending'):
        return 'UNPAID', COLOR_UNPAID
    label = (status or 'UNKNOWN').upper()
    return label, COLOR_MUTED


def _fmt_date(value) -> str:
    if not value:
        return '-'
    if isinstance(value, date):
        return value.strftime('%d %b %Y')
    try:
        return str(value)[:10]
    except Exception:
        return '-'


def _short_id(bill_id) -> str:
    text = str(bill_id or '')
    if len(text) <= 12:
        return text
    return f'{text[:8]}…{text[-4:]}'


def build_bill_pdf_bytes(bill: Bill, *, organization_name: str = 'SmartBasa') -> bytes:
    """Return a professional A4 invoice PDF for one bill."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_x = 16 * mm
    content_w = width - (2 * margin_x)
    right = width - margin_x

    items = list(bill.items.all()) if hasattr(bill, 'items') else []
    status_label, status_color = _status_style(getattr(bill, 'status', None))
    try:
        total = float(bill.amount or 0)
    except (TypeError, ValueError):
        total = 0.0
    try:
        paid = float(bill.amount_paid or 0)
    except (TypeError, ValueError):
        paid = 0.0
    balance = max(total - paid, 0.0)

    # ── Top brand bar ──────────────────────────────────────────────
    bar_h = 22 * mm
    pdf.setFillColor(COLOR_HEADER)
    pdf.rect(0, height - bar_h, width, bar_h, fill=1, stroke=0)

    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(margin_x, height - 11 * mm, _safe(organization_name))
    pdf.setFont('Helvetica', 9)
    pdf.drawString(margin_x, height - 16.5 * mm, 'Property billing receipt')

    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawRightString(right, height - 10 * mm, 'INVOICE')
    pdf.setFont('Helvetica', 9)
    pdf.drawRightString(
        right,
        height - 16 * mm,
        _safe(f'{bill.month} {bill.year}'),
    )

    y = height - bar_h - 10 * mm

    # ── Status chip + bill reference ───────────────────────────────
    chip_w, chip_h = 28 * mm, 7 * mm
    pdf.setFillColor(status_color)
    pdf.roundRect(margin_x, y - 1.5 * mm, chip_w, chip_h, 2 * mm, fill=1, stroke=0)
    pdf.setFillColor(white)
    pdf.setFont('Helvetica-Bold', 9)
    pdf.drawCentredString(margin_x + chip_w / 2, y + 0.7 * mm, status_label)

    pdf.setFillColor(COLOR_MUTED)
    pdf.setFont('Helvetica', 8)
    pdf.drawRightString(right, y + 1.5 * mm, _safe(f'Bill ID  {_short_id(bill.id)}'))
    y -= 12 * mm

    # ── Two info cards: Bill to / Property ──────────────────────────
    card_gap = 4 * mm
    card_w = (content_w - card_gap) / 2
    card_h = 32 * mm

    def _info_card(x: float, title: str, rows: list[tuple[str, str]]):
        pdf.setFillColor(COLOR_HEADER_SOFT)
        pdf.roundRect(x, y - card_h + 4 * mm, card_w, card_h, 2.5 * mm, fill=1, stroke=0)
        pdf.setFillColor(COLOR_HEADER)
        pdf.setFont('Helvetica-Bold', 8)
        pdf.drawString(x + 3.5 * mm, y - 2 * mm, title.upper())
        ty = y - 8 * mm
        for label, value in rows:
            pdf.setFillColor(COLOR_MUTED)
            pdf.setFont('Helvetica', 7.5)
            pdf.drawString(x + 3.5 * mm, ty, label)
            pdf.setFillColor(COLOR_INK)
            pdf.setFont('Helvetica-Bold', 9)
            pdf.drawString(x + 3.5 * mm, ty - 3.8 * mm, _safe(value)[:42])
            ty -= 9 * mm

    _info_card(
        margin_x,
        'Bill to',
        [
            ('Tenant', bill.tenant_name or '-'),
            ('Unit', _unit_label(bill)),
        ],
    )
    _info_card(
        margin_x + card_w + card_gap,
        'Property',
        [
            ('Name', bill.property_name or '-'),
            ('Type', _property_type_label(getattr(bill, 'property_type', None))),
        ],
    )
    y -= card_h + 4 * mm

    # ── Meta strip ─────────────────────────────────────────────────
    meta = [
        ('Period', f'{bill.month} {bill.year}'),
        ('Due date', _fmt_date(bill.due_date)),
        ('Paid date', _fmt_date(getattr(bill, 'paid_date', None))),
        ('Items', str(len(items))),
    ]
    meta_w = content_w / len(meta)
    pdf.setStrokeColor(COLOR_LINE)
    pdf.setLineWidth(0.6)
    pdf.line(margin_x, y + 3 * mm, right, y + 3 * mm)
    for i, (label, value) in enumerate(meta):
        x = margin_x + i * meta_w
        pdf.setFillColor(COLOR_MUTED)
        pdf.setFont('Helvetica', 7)
        pdf.drawString(x, y - 1 * mm, label.upper())
        pdf.setFillColor(COLOR_INK)
        pdf.setFont('Helvetica-Bold', 9)
        pdf.drawString(x, y - 5.5 * mm, _safe(value))
    y -= 14 * mm

    # ── Line items table ───────────────────────────────────────────
    col_no = margin_x
    col_desc = margin_x + 12 * mm
    col_amt = right

    def _table_header(at_y: float) -> float:
        pdf.setFillColor(COLOR_HEADER)
        pdf.roundRect(margin_x, at_y - 2 * mm, content_w, 8 * mm, 1.5 * mm, fill=1, stroke=0)
        pdf.setFillColor(white)
        pdf.setFont('Helvetica-Bold', 8)
        pdf.drawString(col_no + 2 * mm, at_y + 0.5 * mm, '#')
        pdf.drawString(col_desc, at_y + 0.5 * mm, 'DESCRIPTION')
        pdf.drawRightString(col_amt - 2 * mm, at_y + 0.5 * mm, 'AMOUNT')
        return at_y - 10 * mm

    y = _table_header(y)

    if not items:
        pdf.setFillColor(COLOR_MUTED)
        pdf.setFont('Helvetica-Oblique', 9)
        pdf.drawString(col_desc, y, 'No line items')
        y -= 8 * mm
    else:
        for idx, item in enumerate(items, start=1):
            if y < 55 * mm:
                pdf.showPage()
                # Continuation header
                pdf.setFillColor(COLOR_HEADER)
                pdf.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)
                pdf.setFillColor(white)
                pdf.setFont('Helvetica-Bold', 11)
                pdf.drawString(margin_x, height - 8 * mm, _safe(f'{organization_name} — Invoice (cont.)'))
                y = height - 22 * mm
                y = _table_header(y)

            row_h = 8 * mm
            if idx % 2 == 0:
                pdf.setFillColor(COLOR_ROW_ALT)
                pdf.rect(margin_x, y - 2.5 * mm, content_w, row_h, fill=1, stroke=0)

            desc = _safe(item.description or 'Item')
            if len(desc) > 70:
                desc = desc[:67] + '...'

            pdf.setFillColor(COLOR_MUTED)
            pdf.setFont('Helvetica', 8)
            pdf.drawString(col_no + 2 * mm, y, str(idx))
            pdf.setFillColor(COLOR_INK)
            pdf.setFont('Helvetica', 9)
            pdf.drawString(col_desc, y, desc)
            pdf.setFont('Helvetica', 9)
            pdf.drawRightString(col_amt - 2 * mm, y, _money(item.amount))
            y -= row_h

    y -= 4 * mm
    pdf.setStrokeColor(COLOR_LINE)
    pdf.setLineWidth(0.8)
    pdf.line(margin_x, y + 4 * mm, right, y + 4 * mm)
    y -= 2 * mm

    # ── Totals box (right aligned) ─────────────────────────────────
    box_w = 72 * mm
    box_x = right - box_w
    rows_total = [
        ('Subtotal', _money(total), False),
        ('Amount paid', _money(paid), False),
        ('Balance due', _money(balance), True),
    ]
    box_h = 8 * mm + len(rows_total) * 7 * mm
    pdf.setFillColor(COLOR_TOTAL_BG)
    pdf.roundRect(box_x, y - box_h + 5 * mm, box_w, box_h, 2 * mm, fill=1, stroke=0)

    ty = y - 2 * mm
    for label, value, emphasize in rows_total:
        if emphasize:
            pdf.setFillColor(COLOR_HEADER)
            pdf.setFont('Helvetica-Bold', 10)
        else:
            pdf.setFillColor(COLOR_MUTED)
            pdf.setFont('Helvetica', 9)
        pdf.drawString(box_x + 3 * mm, ty, label)
        pdf.setFillColor(COLOR_INK if not emphasize else COLOR_HEADER)
        pdf.setFont('Helvetica-Bold' if emphasize else 'Helvetica', 10 if emphasize else 9)
        pdf.drawRightString(right - 3 * mm, ty, value)
        ty -= 7 * mm

    y = ty - 8 * mm

    # ── Notes / footer ─────────────────────────────────────────────
    if y < 35 * mm:
        pdf.showPage()
        y = height - 25 * mm

    pdf.setStrokeColor(COLOR_LINE)
    pdf.setLineWidth(0.5)
    pdf.line(margin_x, y + 4 * mm, right, y + 4 * mm)

    pdf.setFillColor(COLOR_MUTED)
    pdf.setFont('Helvetica', 8)
    note = (
        'Please pay the balance due by the due date. '
        'For questions, contact your property owner via SmartBasa.'
    )
    pdf.drawString(margin_x, y - 2 * mm, _safe(note))

    pdf.setFont('Helvetica', 7.5)
    pdf.drawString(
        margin_x,
        14 * mm,
        _safe(f'Generated by {organization_name}  ·  Template {PDF_TEMPLATE_VERSION}'),
    )
    pdf.drawRightString(right, 14 * mm, 'Thank you for your payment.')

    # Bottom accent
    pdf.setFillColor(COLOR_HEADER)
    pdf.rect(0, 0, width, 4 * mm, fill=1, stroke=0)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
