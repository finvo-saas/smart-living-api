from django.urls import path

from support.views import ComplaintListCreateView, ComplaintStatusUpdateView

urlpatterns = [
    path('complaints/', ComplaintListCreateView.as_view(), name='complaint-list'),
    path(
        'complaints/<uuid:pk>/status/',
        ComplaintStatusUpdateView.as_view(),
        name='complaint-status',
    ),
]
