"""Shared serializer fields for contact details."""

from rest_framework import serializers

from accounts.phone import normalize_bd_phone
from core.exceptions import InvalidError


def normalize_optional_phone(raw) -> str:
    """E.164 number, or '' when the caller left it empty."""
    value = '' if raw is None else str(raw).strip()
    if not value:
        return ''
    return normalize_bd_phone(value)


class WhatsAppNumberField(serializers.CharField):
    """Optional WhatsApp number, stored E.164; blank clears it."""

    def __init__(self, **kwargs):
        kwargs.setdefault('required', False)
        kwargs.setdefault('allow_blank', True)
        kwargs.setdefault('max_length', 20)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        raw = super().to_internal_value(data)
        try:
            return normalize_optional_phone(raw)
        except InvalidError as exc:
            # Report against this field instead of aborting the whole request.
            raise serializers.ValidationError(str(exc.detail)) from exc
