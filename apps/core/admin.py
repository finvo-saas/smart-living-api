"""Shared Django admin helpers — show created_at / updated_at everywhere they exist."""

from django.contrib import admin

TIMESTAMP_FIELD_NAMES = ('created_at', 'updated_at')


def _model_concrete_field_names(model) -> set[str]:
    return {field.name for field in model._meta.fields}


class TimestampedAdminMixin:
    """
    Automatically expose created_at / updated_at on changelist + change form
    when the model defines them (e.g. via TimestampedModel).
    """

    def get_list_display(self, request):
        display = list(super().get_list_display(request))
        fields = _model_concrete_field_names(self.model)
        for name in TIMESTAMP_FIELD_NAMES:
            if name in fields and name not in display:
                display.append(name)
        return tuple(display)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        fields = _model_concrete_field_names(self.model)
        for name in TIMESTAMP_FIELD_NAMES:
            if name in fields and name not in readonly:
                readonly.append(name)
        return tuple(readonly)


class TimestampedModelAdmin(TimestampedAdminMixin, admin.ModelAdmin):
    """Default ModelAdmin for timestamped models."""
