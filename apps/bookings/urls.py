from django.urls import path

from bookings.views import (
    AdminPropertyBookingsView,
    MyPropertyBookingsView,
    OwnerPropertyBookingsView,
    PropertyBookingDetailView,
    PropertyBookingListCreateView,
    PropertyBookingStatusView,
)
from core.views_sse import BookingUpdatesSSEView

urlpatterns = [
    path('bookings/', PropertyBookingListCreateView.as_view(), name='booking-create'),
    path('bookings/mine/', MyPropertyBookingsView.as_view(), name='booking-mine'),
    path('bookings/owner/', OwnerPropertyBookingsView.as_view(), name='booking-owner'),
    path(
        'bookings/stream/',
        BookingUpdatesSSEView.as_view(),
        name='booking-stream',
    ),
    path('bookings/<uuid:pk>/', PropertyBookingDetailView.as_view(), name='booking-detail'),
    path(
        'bookings/<uuid:pk>/status/',
        PropertyBookingStatusView.as_view(),
        name='booking-status',
    ),
    path('admin/bookings/', AdminPropertyBookingsView.as_view(), name='admin-bookings'),
]
