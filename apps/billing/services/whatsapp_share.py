"""WhatsApp link-share for bills (Approach A — owner opens own WhatsApp)."""

from __future__ import annotations

from urllib.parse import quote

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.phone import PHONE_DIGITS_RE, normalize_bd_phone
from billing.models import Bill, PropertyKind
from billing.services.pdf import build_bill_pdf_bytes
from billing.services.public_pdf import build_public_bill_pdf_url
from core.exceptions import InvalidError
from core.services.media import media_storage
from mess.models import MessStudent
from portfolio.models import Tenancy, TenancyStatus


def _digits_for_wa(raw: str | None) -> str:
    if not raw:
        return ''
    try:
        e164 = normalize_bd_phone(raw)
    except InvalidError:
        digits = PHONE_DIGITS_RE.sub('', str(raw))
        return digits if len(digits) >= 10 else ''
    return PHONE_DIGITS_RE.sub('', e164)


def resolve_bill_whatsapp_number(bill: Bill) -> str:
    """
    Best-effort WhatsApp number for the bill's tenant/member.

    Order: tenancy snapshot → mess member → linked user → empty.
    """
    candidates: list[str] = []

    if bill.property_type == PropertyKind.APARTMENT and bill.flat_id:
        tenancy = (
            Tenancy.objects.filter(flat_id=bill.flat_id, status=TenancyStatus.ACTIVE)
            .select_related('tenant')
            .order_by('-start_date')
            .first()
        )
        if tenancy:
            if tenancy.tenant_whatsapp:
                candidates.append(tenancy.tenant_whatsapp)
            if tenancy.tenant_id and getattr(tenancy.tenant, 'whatsapp_number', ''):
                candidates.append(tenancy.tenant.whatsapp_number)
            if tenancy.tenant_id and getattr(tenancy.tenant, 'phone', ''):
                candidates.append(tenancy.tenant.phone)

    if bill.property_type == PropertyKind.MESS:
        student = None
        snapshot = (bill.tenant_id_snapshot or '').strip()
        if snapshot:
            try:
                student = (
                    MessStudent.objects.filter(pk=snapshot, is_deleted=False)
                    .select_related('user')
                    .first()
                )
            except (ValueError, TypeError):
                student = None
        if not student and bill.tenant_id:
            student = (
                MessStudent.objects.filter(
                    mess_id=bill.property_id,
                    user_id=bill.tenant_id,
                    is_deleted=False,
                    is_active=True,
                )
                .select_related('user')
                .order_by('-joined_date')
                .first()
            )
        if not student and bill.seat_number:
            student = (
                MessStudent.objects.filter(
                    mess_id=bill.property_id,
                    seat_number=bill.seat_number,
                    is_deleted=False,
                    is_active=True,
                )
                .select_related('user')
                .order_by('-joined_date')
                .first()
            )
        if student:
            if student.whatsapp_number:
                candidates.append(student.whatsapp_number)
            if student.phone:
                candidates.append(student.phone)
            if student.user_id and getattr(student.user, 'whatsapp_number', ''):
                candidates.append(student.user.whatsapp_number)
            if student.user_id and getattr(student.user, 'phone', ''):
                candidates.append(student.user.phone)

    if bill.tenant_id:
        user = bill.tenant
        if user:
            if getattr(user, 'whatsapp_number', ''):
                candidates.append(user.whatsapp_number)
            if getattr(user, 'phone', ''):
                candidates.append(user.phone)

    for raw in candidates:
        digits = _digits_for_wa(raw)
        if digits:
            return digits
    return ''


def _share_message(bill: Bill, pdf_url: str) -> str:
    unit = ''
    if bill.flat_number:
        unit = f' (Flat {bill.flat_number})'
    elif bill.seat_number:
        unit = f' (Seat {bill.seat_number})'
    amount = f'{float(bill.amount):,.2f}'
    due = bill.due_date.isoformat() if bill.due_date else '-'
    return (
        f'SmartBasa bill for {bill.tenant_name}\n'
        f'{bill.property_name}{unit}\n'
        f'{bill.month} {bill.year} — BDT {amount}\n'
        f'Due: {due} | Status: {bill.status}\n'
        f'Download PDF: {pdf_url}'
    )


def ensure_bill_pdf(bill: Bill, *, force: bool = False, request=None) -> tuple[str, str]:
    """
    Ensure a public PDF exists for the bill on DigitalOcean Spaces.

    Path: ``{STORAGE_ROOT_FOLDER}/media/bills/<uuid>.pdf`` (public CDN URL).

    Returns (pdf_url, pdf_key).
    """
    from django.conf import settings

    from billing.services.pdf import PDF_TEMPLATE_VERSION

    if not getattr(settings, 'USE_OBJECT_STORAGE', False):
        raise InvalidError(
            'Bill PDFs require DigitalOcean Spaces. '
            'Set STORAGE_PROVIDER=digitalocean and DO_SPACES_* credentials.'
        )

    version_tag = f'tpl={PDF_TEMPLATE_VERSION}'
    # Reuse only current template version on Spaces under media/bills/.
    if (
        not force
        and bill.pdf_url
        and bill.pdf_key
        and bill.pdf_url.startswith('http')
        and version_tag in bill.pdf_url
        and (
            bill.pdf_key.startswith('media/bills/')
            or bill.pdf_key.startswith('bills/')
        )
    ):
        return bill.pdf_url, bill.pdf_key

    if 'items' not in getattr(bill, '_prefetched_objects_cache', {}):
        bill = Bill.objects.prefetch_related('items').get(pk=bill.pk)

    pdf_bytes = build_bill_pdf_bytes(bill)
    filename = (
        f'bill-{bill.id}-{bill.month}-{bill.year}-{PDF_TEMPLATE_VERSION}.pdf'
    ).replace(' ', '-')
    uploaded = SimpleUploadedFile(filename, pdf_bytes, content_type='application/pdf')
    stored = media_storage.upload(uploaded, 'bill', request=request)
    url = stored.url
    sep = '&' if '?' in url else '?'
    bill.pdf_url = f'{url}{sep}{version_tag}'
    bill.pdf_key = stored.key
    bill.save(update_fields=['pdf_url', 'pdf_key', 'updated_at'])
    return bill.pdf_url, bill.pdf_key


def prepare_whatsapp_share(
    bill: Bill,
    *,
    regenerate_pdf: bool = False,
    request=None,
) -> dict:
    """
    Build WhatsApp deep-link payload for the bill owner.

    Opens the owner's WhatsApp app/chat with the renter number and a PDF link.
    """
    whatsapp_number = resolve_bill_whatsapp_number(bill)
    if not whatsapp_number:
        raise InvalidError(
            'No WhatsApp number found for this tenant. '
            'Add their WhatsApp number on the tenancy or member profile.'
        )

    pdf_url, pdf_key = ensure_bill_pdf(
        bill, force=regenerate_pdf, request=request
    )
    # Prefer branded system URL in WhatsApp; CDN stays the storage backend.
    share_pdf_url = build_public_bill_pdf_url(bill, request=request)
    message = _share_message(bill, share_pdf_url)
    whatsapp_url = (
        f'https://wa.me/{whatsapp_number}?text={quote(message)}'
    )

    bill.whatsapp_shared_at = timezone.now()
    bill.save(update_fields=['whatsapp_shared_at', 'updated_at'])

    return {
        'billId': str(bill.id),
        'tenantName': bill.tenant_name,
        'whatsappNumber': f'+{whatsapp_number}',
        'whatsappUrl': whatsapp_url,
        'pdfUrl': share_pdf_url,
        'storagePdfUrl': pdf_url,
        'pdfKey': pdf_key,
        'message': message,
        'sharedAt': timezone.localtime(bill.whatsapp_shared_at).isoformat(),
    }


def _due_reminder_message(bill: Bill) -> str:
    unit = ''
    if bill.flat_number:
        unit = f' (Flat {bill.flat_number})'
    elif bill.seat_number:
        unit = f' (Seat {bill.seat_number})'
    amount = f'{float(bill.amount):,.0f}'
    due = bill.due_date.isoformat() if bill.due_date else '-'
    status = (bill.status or 'unpaid').upper()
    return (
        f'SmartBasa rent reminder\n'
        f'{bill.property_name}{unit}\n'
        f'{bill.month} {bill.year} — BDT {amount}\n'
        f'Due: {due} | Status: {status}\n'
        f'Please pay at your earliest convenience. '
        f'Thank you — {bill.property_name} management.'
    )


def prepare_whatsapp_due_reminder(bill: Bill) -> dict:
    """
    Lightweight due reminder (no PDF). Opens owner's WhatsApp to the tenant.
    """
    whatsapp_number = resolve_bill_whatsapp_number(bill)
    if not whatsapp_number:
        raise InvalidError(
            'No WhatsApp number found for this tenant. '
            'Add their WhatsApp number on the tenancy or member profile.'
        )
    message = _due_reminder_message(bill)
    whatsapp_url = f'https://wa.me/{whatsapp_number}?text={quote(message)}'
    bill.whatsapp_shared_at = timezone.now()
    bill.save(update_fields=['whatsapp_shared_at', 'updated_at'])
    return {
        'billId': str(bill.id),
        'tenantName': bill.tenant_name,
        'whatsappNumber': f'+{whatsapp_number}',
        'whatsappUrl': whatsapp_url,
        'message': message,
        'sharedAt': timezone.localtime(bill.whatsapp_shared_at).isoformat(),
        'channel': 'whatsapp',
    }


def send_sms_due_reminder(bill: Bill) -> dict:
    """Send a due reminder SMS to the tenant phone (gateway / console)."""
    from accounts.services.sms import send_sms

    phone_digits = resolve_bill_whatsapp_number(bill)
    phone = ''
    if phone_digits:
        phone = phone_digits if phone_digits.startswith('+') else f'+{phone_digits}'
    elif bill.tenant_id and getattr(bill.tenant, 'phone', ''):
        try:
            phone = normalize_bd_phone(bill.tenant.phone)
        except InvalidError:
            phone = ''
    if not phone:
        raise InvalidError('No phone number found for this tenant.')

    message = _due_reminder_message(bill)
    result = send_sms(phone, message)
    return {
        'billId': str(bill.id),
        'tenantName': bill.tenant_name,
        'phone': phone,
        'message': message,
        'channel': 'sms',
        'delivered': bool(result.get('delivered')),
        'providerChannel': result.get('channel'),
    }
