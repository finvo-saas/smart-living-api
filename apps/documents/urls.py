from django.urls import path

from documents.views import (
    AgreementActiveView,
    AgreementDetailView,
    AgreementFormDataView,
    AgreementListCreateView,
    AgreementRenewalCreateView,
    AgreementSignView,
    ChecklistCategoriesView,
    ChecklistDetailView,
    ChecklistListCreateView,
    PRCAGenerateTermsView,
    PRCATemplateListView,
)

urlpatterns = [
    path('agreements/', AgreementListCreateView.as_view(), name='agreement-list'),
    path('agreements/active/', AgreementActiveView.as_view(), name='agreement-active'),
    path('agreements/form-data/', AgreementFormDataView.as_view(), name='agreement-form-data'),
    path('agreements/templates/', PRCATemplateListView.as_view(), name='prca-templates'),
    path(
        'agreements/generate-terms/',
        PRCAGenerateTermsView.as_view(),
        name='prca-generate-terms',
    ),
    path('agreements/<uuid:pk>/', AgreementDetailView.as_view(), name='agreement-detail'),
    path(
        'agreements/<uuid:pk>/sign/',
        AgreementSignView.as_view(),
        name='agreement-sign',
    ),
    path(
        'agreements/<uuid:pk>/renewals/',
        AgreementRenewalCreateView.as_view(),
        name='agreement-renewal',
    ),
    path('checklists/', ChecklistListCreateView.as_view(), name='checklist-list'),
    path(
        'checklists/categories/',
        ChecklistCategoriesView.as_view(),
        name='checklist-categories',
    ),
    path('checklists/<uuid:pk>/', ChecklistDetailView.as_view(), name='checklist-detail'),
]
