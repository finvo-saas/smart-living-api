from django.urls import path

from hotels.views import (
    HotelBookingCancelView,
    HotelBookingsView,
    HotelDetailView,
    HotelListCreateView,
    HotelPricingUpdateView,
    HotelReviewListCreateView,
    HotelRoomDetailView,
    HotelRoomListCreateView,
    MyHotelBookingsView,
    OwnerHotelsView,
    RoomPricingDetailView,
    RoomPricingListView,
)

urlpatterns = [
    path('hotels/', HotelListCreateView.as_view(), name='hotel-list'),
    path('hotels/mine/', OwnerHotelsView.as_view(), name='hotel-mine'),
    path('hotels/bookings/mine/', MyHotelBookingsView.as_view(), name='hotel-booking-mine'),
    path(
        'hotels/bookings/<uuid:booking_id>/cancel/',
        HotelBookingCancelView.as_view(),
        name='hotel-booking-cancel',
    ),
    path('hotels/<uuid:pk>/', HotelDetailView.as_view(), name='hotel-detail'),
    path(
        'hotels/<uuid:pk>/pricing/',
        HotelPricingUpdateView.as_view(),
        name='hotel-pricing',
    ),
    path(
        'hotels/<uuid:pk>/rooms/',
        HotelRoomListCreateView.as_view(),
        name='hotel-rooms',
    ),
    path(
        'hotels/<uuid:pk>/rooms/pricing/',
        RoomPricingListView.as_view(),
        name='hotel-room-pricing',
    ),
    path(
        'hotels/<uuid:pk>/rooms/<uuid:room_id>/pricing/',
        RoomPricingDetailView.as_view(),
        name='hotel-room-pricing-detail',
    ),
    path(
        'hotels/<uuid:pk>/rooms/<uuid:room_id>/',
        HotelRoomDetailView.as_view(),
        name='hotel-room-detail',
    ),
    path(
        'hotels/<uuid:pk>/bookings/',
        HotelBookingsView.as_view(),
        name='hotel-bookings',
    ),
    path(
        'hotels/<uuid:pk>/reviews/',
        HotelReviewListCreateView.as_view(),
        name='hotel-reviews',
    ),
]
