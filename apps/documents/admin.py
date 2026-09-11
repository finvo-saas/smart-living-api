from django.contrib import admin

from core.admin import TimestampedModelAdmin
from documents.models import AgreementRenewal, Checklist, RentalAgreement


@admin.register(RentalAgreement)
class RentalAgreementAdmin(TimestampedModelAdmin):
    list_display = (
        'property_name',
        'flat_number',
        'status',
        'user',
        'start_date',
        'end_date',
    )
    list_filter = ('status', 'agreement_type')
    search_fields = ('property_name', 'user__phone', 'document_name')


@admin.register(AgreementRenewal)
class AgreementRenewalAdmin(TimestampedModelAdmin):
    list_display = ('agreement', 'new_start_date', 'new_end_date', 'new_monthly_rent')
    search_fields = ('agreement__property_name',)


@admin.register(Checklist)
class ChecklistAdmin(TimestampedModelAdmin):
    list_display = ('property_name', 'type', 'status', 'user')
    list_filter = ('type', 'status')
    search_fields = ('property_name', 'user__phone')
