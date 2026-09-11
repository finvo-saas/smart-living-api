from django.urls import path

from ops.views import (
    BuildingScopeNoticeView,
    HotelScopeNoticeView,
    UnifiedNoticeAckView,
    UnifiedNoticeDetailView,
    UnifiedNoticeFeedView,
)

urlpatterns = [
    # Unified feed (also mounted as /notices/ from mess urls for back-compat)
    path('ops/notices/', UnifiedNoticeFeedView.as_view(), name='ops-notice-feed'),
    path(
        'ops/notices/<uuid:notice_id>/',
        UnifiedNoticeDetailView.as_view(),
        name='ops-notice-detail',
    ),
    path(
        'ops/notices/<uuid:notice_id>/acknowledge/',
        UnifiedNoticeAckView.as_view(),
        name='ops-notice-ack',
    ),
    path(
        'buildings/<uuid:building_id>/notices/',
        BuildingScopeNoticeView.as_view(),
        name='building-notices',
    ),
    path(
        'building-notices/',
        UnifiedNoticeFeedView.as_view(),
        name='building-notice-feed',
    ),
    path(
        'building-notices/<uuid:notice_id>/',
        UnifiedNoticeDetailView.as_view(),
        name='building-notice-detail',
    ),
    path(
        'building-notices/<uuid:notice_id>/acknowledge/',
        UnifiedNoticeAckView.as_view(),
        name='building-notice-ack',
    ),
    path(
        'hotels/<uuid:hotel_id>/notices/',
        HotelScopeNoticeView.as_view(),
        name='hotel-notices',
    ),
]
