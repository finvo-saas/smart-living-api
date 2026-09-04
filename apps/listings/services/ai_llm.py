"""Optional LLM parse for natural-language housing queries (OpenAI-compatible)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings

logger = logging.getLogger('listings.ai_llm')


def llm_parse_query(query: str) -> dict[str, Any] | None:
    """
    Call an OpenAI-compatible Chat Completions API to extract structured filters.
    Returns None when disabled, unconfigured, or on any failure (caller falls back).
    """
    if not getattr(settings, 'AI_MATCH_LLM_ENABLED', False):
        return None
    api_key = (getattr(settings, 'AI_MATCH_LLM_API_KEY', '') or '').strip()
    if not api_key:
        return None

    base = (getattr(settings, 'AI_MATCH_LLM_BASE_URL', '') or 'https://api.openai.com/v1').rstrip('/')
    model = getattr(settings, 'AI_MATCH_LLM_MODEL', 'gpt-4o-mini') or 'gpt-4o-mini'

    system = (
        'You extract Bangladesh housing search filters from Bangla or English. '
        'Reply with ONLY compact JSON keys: area (string|null), city (string|null), '
        'type (apartment|mess|hostel|null), gender (male|female|mixed|null), '
        'budgetMin (number|null), budgetMax (number|null), bedrooms (int|null), '
        'facilities (string array). Use English lowercase area/city names when known '
        '(mohammadpur, dhanmondi, dhaka, …). facilities examples: lift, wifi, generator, ac, parking, security, balcony.'
    )
    body = {
        'model': model,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': query[:800]},
        ],
    }
    req = urllib.request.Request(
        f'{base}/chat/completions',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        content = payload['choices'][0]['message']['content']
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None
        return _normalize_llm_parsed(parsed, query)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        logger.warning('LLM parse failed, using rules: %s', exc)
        return None


def _normalize_llm_parsed(raw: dict, query: str) -> dict[str, Any]:
    facilities = raw.get('facilities') or []
    if isinstance(facilities, str):
        facilities = [f.strip() for f in facilities.split(',') if f.strip()]
    budget_min = raw.get('budgetMin')
    budget_max = raw.get('budgetMax')
    try:
        budget_min = float(budget_min) if budget_min is not None else None
    except (TypeError, ValueError):
        budget_min = None
    try:
        budget_max = float(budget_max) if budget_max is not None else None
    except (TypeError, ValueError):
        budget_max = None
    bedrooms = raw.get('bedrooms')
    try:
        bedrooms = int(bedrooms) if bedrooms is not None else None
    except (TypeError, ValueError):
        bedrooms = None
    ptype = raw.get('type')
    if ptype not in ('apartment', 'mess', 'hostel', None):
        ptype = None
    gender = raw.get('gender')
    if gender not in ('male', 'female', 'mixed', None):
        gender = None
    return {
        'area': (raw.get('area') or None) and str(raw['area']).strip().lower() or None,
        'city': (raw.get('city') or None) and str(raw['city']).strip().lower() or None,
        'type': ptype,
        'gender': gender,
        'budgetMin': budget_min,
        'budgetMax': budget_max,
        'bedrooms': bedrooms,
        'facilities': [str(f).lower() for f in facilities][:12],
        'rawQuery': query,
        'parser': 'llm',
    }
