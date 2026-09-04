"""PRCA stamp duty guidance and rent-increase helpers."""
from __future__ import annotations

from datetime import date
from typing import Any


def stamp_duty_guidance(
    *,
    monthly_rent: float,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """
    Bangladesh practice: leases over 1 year typically need registration + stamp duty.
    This is guidance only — rates vary by instrument and jurisdiction.
    """
    months = max(
        1,
        (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month),
    )
    annual_rent = float(monthly_rent) * 12
    requires_registration = months > 12
    # Indicative stamp duty band used for UX (not legal advice)
    indicative_rate = 0.02 if requires_registration else 0.0
    indicative_amount = round(annual_rent * indicative_rate, 2) if requires_registration else 0.0

    notes = []
    if requires_registration:
        notes.append(
            'Agreements exceeding one year typically require registration under '
            'applicable stamp / registration rules. Confirm current rates with a '
            'sub-registrar or licensed lawyer.',
        )
        notes.append(
            f'Indicative stamp duty estimate (~2% of annual rent ৳{annual_rent:,.0f}): '
            f'৳{indicative_amount:,.0f}. This is not a legal calculation.',
        )
    else:
        notes.append(
            'Monthly tenancies of 12 months or less often do not require full '
            'registration, but written PRCA-compliant terms and rent receipts remain mandatory.',
        )

    return {
        'durationMonths': months,
        'annualRent': annual_rent,
        'requiresRegistration': requires_registration,
        'indicativeStampDutyRate': indicative_rate,
        'indicativeStampDutyAmount': indicative_amount,
        'notes': notes,
    }


def rent_increase_rules(monthly_rent: float) -> dict[str, Any]:
    return {
        'currentRent': float(monthly_rent),
        'allowedOnlyWhen': [
            'Structural improvements approved under PRCA Sections 15–16',
            'Documented increase in municipal taxes or similar statutory charges',
            'Mutual written agreement that still respects standard rent principles',
        ],
        'prohibited': [
            'Arbitrary annual increase without statutory grounds',
            'Charging salami / premium beyond lawful rent (Section 10)',
        ],
        'receiptRequired': True,
        'summary': (
            'Under PRCA 1991, landlords cannot raise rent arbitrarily. Increases must '
            'follow Sections 15–16. Every rent payment requires a written receipt (Section 23).'
        ),
    }
