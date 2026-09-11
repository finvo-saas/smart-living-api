from django.urls import path

from support.views import (
    ComplaintListCreateView,
    ComplaintMessageListCreateView,
    ComplaintStatusUpdateView,
)

urlpatterns = [
    path('complaints/', ComplaintListCreateView.as_view(), name='complaint-list'),
    path(
        'complaints/<uuid:pk>/status/',
        ComplaintStatusUpdateView.as_view(),
        name='complaint-status',
    ),
    path(
        'complaints/<uuid:pk>/messages/',
        ComplaintMessageListCreateView.as_view(),
        name='complaint-messages',
    ),
]
