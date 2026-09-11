"""Public branded URLs for bill PDFs (redirect to Spaces)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from django.utils.text import slugify

from billing.models import Bill


def property_slug_for_bill(bill: Bill) -> str:
    slug = slugify(bill.property_name or '') or slugify(str(bill.property_id or ''))
    return slug or 'property'


def pdf_file_id_from_key(pdf_key: str) -> str:
    """``media/bills/<hex>.pdf`` → ``<hex>``."""
    stem = Path((pdf_key or '').replace('\\', '/')).name
    if stem.lower().endswith('.pdf'):
        stem = stem[:-4]
    return stem


def storage_url_without_template_tag(pdf_url: str) -> str:
    """Strip tpl= version query so PDF clients get a clean CDN URL."""
    if not pdf_url:
        return ''
    parsed = urlparse(pdf_url)
    if not parsed.query:
        return pdf_url
    parts = [
        p
        for p in parsed.query.split('&')
        if p and not p.startswith('tpl=')
    ]
    return urlunparse(parsed._replace(query='&'.join(parts)))


def public_api_base(*, request=None) -> str:
    """
    Absolute API prefix including ``/api/v1``.

    Prefer PUBLIC_API_URL (same as frontend deploy), else request host.
    """
    configured = (getattr(settings, 'PUBLIC_API_URL', '') or '').strip().rstrip('/')
    if configured:
        return configured
    if request is not None:
        return request.build_absolute_uri('/api/v1').rstrip('/')
    frontend = (getattr(settings, 'FRONTEND_URL', '') or '').rstrip('/')
    # Local default when API runs on :8000
    if 'localhost:3000' in frontend:
        return 'http://127.0.0.1:8000/api/v1'
    return f'{frontend}/api/v1' if frontend else 'http://127.0.0.1:8000/api/v1'


def build_public_bill_pdf_url(bill: Bill, *, request=None) -> str:
    """
    Branded public link, e.g.::

        https://api.example.com/api/v1/public/bills/green-valley-mess/<file>.pdf
    """
    file_id = pdf_file_id_from_key(bill.pdf_key)
    if not file_id:
        return storage_url_without_template_tag(bill.pdf_url)
    slug = property_slug_for_bill(bill)
    base = public_api_base(request=request)
    return f'{base}/public/bills/{slug}/{file_id}.pdf'


def resolve_bill_for_public_pdf(property_slug: str, file_id: str) -> Bill | None:
    file_id = (file_id or '').strip().lower()
    if not file_id or len(file_id) < 8:
        return None
    # Keys are ``media/bills/<uuidhex>.pdf`` (and legacy ``bills/…``).
    candidates = Bill.objects.filter(
        is_deleted=False,
        pdf_key__iendswith=f'/{file_id}.pdf',
    ).order_by('-updated_at')[:5]
    slug = (property_slug or '').strip().lower()
    for bill in candidates:
        if property_slug_for_bill(bill) == slug:
            return bill
    # Soft match: file id is unique enough if slug drifted after rename.
    return candidates[0] if candidates else None
