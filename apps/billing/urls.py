from django.urls import path

from billing.views import (
    ActiveBillRulesView,
    ActiveBillTemplatesView,
    BillDetailView,
    BillRulesBulkView,
    BillTemplatesBulkView,
    BillTemplatesByPropertyView,
    BillsBoardView,
    BillsBulkView,
    BulkGenerateBillsView,
    CurrentMeterReadingView,
    GenerateBillView,
    MarkBillPaidView,
    MeterReadingsBulkView,
    OwnerBillsView,
    PreviousMeterReadingView,
    TenantBillsView,
)

urlpatterns = [
    path('bills/board/', BillsBoardView.as_view(), name='bills-board'),
    path('bills/mine/', TenantBillsView.as_view(), name='bills-mine'),
    path('bills/owner/', OwnerBillsView.as_view(), name='bills-owner'),
    path('bills/bulk/', BillsBulkView.as_view(), name='bills-bulk'),
    path('bills/generate/', GenerateBillView.as_view(), name='bills-generate'),
    path('bills/bulk-generate/', BulkGenerateBillsView.as_view(), name='bills-bulk-generate'),
    path('bills/<uuid:pk>/', BillDetailView.as_view(), name='bill-detail'),
    path('bills/<uuid:pk>/mark-paid/', MarkBillPaidView.as_view(), name='bill-mark-paid'),
    path('bill-templates/bulk/', BillTemplatesBulkView.as_view(), name='bill-templates-bulk'),
    path(
        'bill-templates/active/',
        ActiveBillTemplatesView.as_view(),
        name='bill-templates-active',
    ),
    path('bill-templates/', BillTemplatesByPropertyView.as_view(), name='bill-templates'),
    path('bill-rules/bulk/', BillRulesBulkView.as_view(), name='bill-rules-bulk'),
    path('bill-rules/active/', ActiveBillRulesView.as_view(), name='bill-rules-active'),
    path('meter-readings/bulk/', MeterReadingsBulkView.as_view(), name='meter-readings-bulk'),
    path(
        'meter-readings/previous/',
        PreviousMeterReadingView.as_view(),
        name='meter-readings-previous',
    ),
    path(
        'meter-readings/current/',
        CurrentMeterReadingView.as_view(),
        name='meter-readings-current',
    ),
]
