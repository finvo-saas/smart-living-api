"""PRCA 1991 compliant rental agreement template engine."""

from __future__ import annotations

from datetime import date
from typing import Any


PRCA_PROVISIONS = {
    'standard_rent': {
        'section': 'Section 7',
        'title': 'Standard Rent',
        'description': (
            'The monthly rent shall not exceed the standard rent as defined '
            'under Section 7 of the Premises Rent Control Act, 1991. '
            'The landlord shall not charge any premium or salami (Section 10).'
        ),
    },
    'rent_increase': {
        'section': 'Sections 15-16',
        'title': 'Rent Increase Restriction',
        'description': (
            'Rent increase is permissible only under conditions specified in '
            'Sections 15 and 16 of the PRCA 1991, such as structural improvements '
            'or increase in municipal taxes. Arbitrary rent increase is prohibited.'
        ),
    },
    'eviction_protection': {
        'section': 'Section 18',
        'title': 'Eviction Protection',
        'description': (
            'The tenant cannot be evicted without lawful grounds as specified in '
            'Section 18 of the PRCA 1991. Even after lease expiry, the tenant has '
            'statutory tenancy rights and can continue in possession.'
        ),
    },
    'rent_receipt': {
        'section': 'Section 23',
        'title': 'Rent Receipt Obligation',
        'description': (
            'The landlord must provide a receipt for every rent payment made by '
            'the tenant. Failure to provide receipts is a punishable offense '
            'under Section 23 of the PRCA 1991.'
        ),
    },
    'deposit_terms': {
        'section': 'Common Practice',
        'title': 'Security Deposit',
        'description': (
            "Security deposit shall not exceed the equivalent of two months' rent "
            'for residential premises. The deposit is refundable upon vacating, '
            'subject to deductions for damages beyond normal wear and tear.'
        ),
    },
    'notice_period': {
        'section': 'Section 106, TPA 1882',
        'title': 'Notice Period',
        'description': (
            'Either party must provide written notice before termination. '
            "For monthly tenancy: 15 days' notice. For yearly tenancy: 6 months' notice. "
            'Notice must expire at the end of a month of tenancy.'
        ),
    },
    'maintenance': {
        'section': 'General',
        'title': 'Maintenance Responsibility',
        'description': (
            'The landlord is responsible for structural repairs and major maintenance. '
            'The tenant is responsible for day-to-day upkeep and minor repairs caused '
            'by normal use.'
        ),
    },
    'subletting': {
        'section': 'Section 18(1)(b)',
        'title': 'Subletting Restriction',
        'description': (
            'The tenant shall not sublet the premises in whole or part without '
            'the prior written consent of the landlord. Unauthorized subletting '
            'is grounds for eviction under Section 18(1)(b).'
        ),
    },
}


AGREEMENT_TEMPLATES = {
    'residential_monthly': {
        'name': 'Residential Monthly Rental Agreement',
        'namebn': 'আবাসিক মাসিক ভাড়া চুক্তিপত্র',
        'type': 'rental',
        'defaultDurationMonths': 12,
        'defaultNoticeDays': 15,
        'maxDepositMonths': 2,
        'provisions': [
            'standard_rent',
            'rent_increase',
            'eviction_protection',
            'rent_receipt',
            'deposit_terms',
            'notice_period',
            'maintenance',
            'subletting',
        ],
    },
    'mess_seat': {
        'name': 'Mess / Hostel Seat Agreement',
        'namebn': 'মেস / হোস্টেল সিট চুক্তিপত্র',
        'type': 'rental',
        'defaultDurationMonths': 6,
        'defaultNoticeDays': 15,
        'maxDepositMonths': 1,
        'provisions': [
            'standard_rent',
            'rent_receipt',
            'notice_period',
        ],
    },
    'sublease': {
        'name': 'Sublease Agreement',
        'namebn': 'সাবলেট চুক্তিপত্র',
        'type': 'sublease',
        'defaultDurationMonths': 6,
        'defaultNoticeDays': 15,
        'maxDepositMonths': 2,
        'provisions': [
            'standard_rent',
            'rent_receipt',
            'deposit_terms',
            'notice_period',
            'subletting',
        ],
    },
    'commercial': {
        'name': 'Commercial Lease Agreement',
        'namebn': 'বাণিজ্যিক ভাড়া চুক্তিপত্র',
        'type': 'lease',
        'defaultDurationMonths': 12,
        'defaultNoticeDays': 30,
        'maxDepositMonths': 3,
        'provisions': [
            'standard_rent',
            'rent_increase',
            'eviction_protection',
            'rent_receipt',
            'deposit_terms',
            'notice_period',
            'maintenance',
        ],
    },
}


def get_template_list() -> list[dict[str, Any]]:
    result = []
    for key, tmpl in AGREEMENT_TEMPLATES.items():
        provisions = [
            {**PRCA_PROVISIONS[p], 'key': p}
            for p in tmpl['provisions']
            if p in PRCA_PROVISIONS
        ]
        result.append({
            'key': key,
            'name': tmpl['name'],
            'nameBn': tmpl['namebn'],
            'type': tmpl['type'],
            'defaultDurationMonths': tmpl['defaultDurationMonths'],
            'defaultNoticeDays': tmpl['defaultNoticeDays'],
            'maxDepositMonths': tmpl['maxDepositMonths'],
            'provisions': provisions,
        })
    return result


def generate_terms(
    template_key: str,
    *,
    monthly_rent: float,
    deposit: float,
    start_date: date,
    end_date: date,
    notice_days: int | None = None,
    special_conditions: list[str] | None = None,
    landlord_name: str = '',
    tenant_name: str = '',
    property_address: str = '',
) -> dict[str, Any]:
    tmpl = AGREEMENT_TEMPLATES.get(template_key) or AGREEMENT_TEMPLATES['residential_monthly']

    duration_months = max(
        1,
        (end_date.year - start_date.year) * 12 + end_date.month - start_date.month,
    )
    max_deposit = monthly_rent * tmpl['maxDepositMonths']
    effective_notice = notice_days or tmpl['defaultNoticeDays']

    provisions = [
        {**PRCA_PROVISIONS[p], 'key': p}
        for p in tmpl['provisions']
        if p in PRCA_PROVISIONS
    ]

    warnings = []
    if deposit > max_deposit:
        warnings.append(
            f'Security deposit (৳{deposit:,.0f}) exceeds recommended maximum '
            f'of {tmpl["maxDepositMonths"]} months\' rent (৳{max_deposit:,.0f}). '
            'This may not be enforceable under common practice.',
        )

    from documents.services.stamp_duty import rent_increase_rules, stamp_duty_guidance

    stamp = stamp_duty_guidance(
        monthly_rent=monthly_rent,
        start_date=start_date,
        end_date=end_date,
    )
    warnings.extend(stamp.get('notes') or [])

    return {
        'templateKey': template_key,
        'templateName': tmpl['name'],
        'templateNameBn': tmpl['namebn'],
        'duration': duration_months,
        'noticePeriod': effective_notice,
        'maxDepositMonths': tmpl['maxDepositMonths'],
        'provisions': provisions,
        'renewalTerms': (
            'This agreement may be renewed by mutual consent of both parties. '
            'The tenant retains statutory tenancy rights under Section 18 of PRCA 1991 '
            'upon expiry of the contractual term.'
        ),
        'specialConditions': special_conditions or [],
        'warnings': warnings,
        'landlordName': landlord_name,
        'tenantName': tenant_name,
        'propertyAddress': property_address,
        'prcaCompliant': True,
        'generatedAt': date.today().isoformat(),
        'stampDuty': stamp,
        'rentIncreaseRules': rent_increase_rules(monthly_rent),
        'receiptObligation': (
            'Landlord must issue a written rent receipt for every payment '
            '(PRCA 1991 Section 23). Smart Living auto-issues a digital receipt '
            'when rent is paid through the platform.'
        ),
    }
