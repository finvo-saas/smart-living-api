"""Issue mandatory rent receipts after successful rent payments (PRCA §23)."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger('documents.receipts')


def issue_rent_receipt_for_transaction(txn) -> dict | None:
    """Best-effort rent receipt after payment — never breaks payment flow."""
    try:
        from reports.models import TaxDocument, TaxDocumentType
    except Exception:
        return None

    user = getattr(txn, 'user', None)
    if user is None:
        return None

    amount = Decimal(str(getattr(txn, 'amount', 0) or 0))
    if amount <= 0:
        return None

    today = timezone.now().date()
    month_start = today.replace(day=1)
    try:
        doc = TaxDocument.objects.create(
            user=user,
            tax_year=today.year,
            document_type=TaxDocumentType.RENT_RECEIPT,
            period_start=month_start,
            period_end=today,
            total_amount=amount,
            breakdown=[
                {
                    'label': getattr(txn, 'bill_name', None) or 'Rent payment',
                    'amount': float(amount),
                    'transactionId': str(txn.id),
                    'propertyName': getattr(txn, 'property_name', '') or '',
                    'issuedUnder': 'PRCA 1991 Section 23',
                },
            ],
            file_url='',
            file_name=f'rent-receipt-{txn.id}.json',
            verified=True,
            verified_at=timezone.now(),
            verified_by='system',
        )
        try:
            from accounts.services.email import notify_channels

            notify_channels(
                user,
                title='Rent receipt ready',
                body=f'Your receipt for ৳{float(amount):,.0f} is available in Reports.',
                url='/reports',
                email_subject='Rent receipt — SmartBasa',
            )
        except Exception:
            logger.exception('Receipt notify failed')
        return {'id': str(doc.id), 'amount': float(amount)}
    except Exception:
        logger.exception('Failed to issue rent receipt')
        return None
