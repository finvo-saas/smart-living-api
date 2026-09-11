from django.urls import path

from portfolio.views import (
    BuildingAllListView,
    BuildingDetailView,
    BuildingFlatListView,
    BuildingFloorListCreateView,
    BuildingListCreateView,
    FlatAssignRenterView,
    FlatDetailView,
    FlatEnsureListingView,
    FlatListCreateView,
    FlatVacateView,
    FloorDetailView,
    FloorStatsView,
    MyTenanciesView,
    PortfolioSnapshotView,
    RenterHistoryView,
    RenterListView,
)
from portfolio.views_notices import (
    BuildingNoticeAckView,
    BuildingNoticeDetailView,
    BuildingNoticeFeedView,
    BuildingNoticeListCreateView,
)

urlpatterns = [
    path('buildings/', BuildingListCreateView.as_view(), name='building-list'),
    path('buildings/all/', BuildingAllListView.as_view(), name='building-all'),
    path('buildings/<uuid:pk>/', BuildingDetailView.as_view(), name='building-detail'),
    path(
        'buildings/<uuid:building_id>/floors/',
        BuildingFloorListCreateView.as_view(),
        name='building-floors',
    ),
    path(
        'buildings/<uuid:building_id>/flats/',
        BuildingFlatListView.as_view(),
        name='building-flats',
    ),
    path(
        'buildings/<uuid:building_id>/notices/',
        BuildingNoticeListCreateView.as_view(),
        name='building-notices',
    ),
    path('building-notices/', BuildingNoticeFeedView.as_view(), name='building-notice-feed'),
    path(
        'building-notices/<uuid:notice_id>/',
        BuildingNoticeDetailView.as_view(),
        name='building-notice-detail',
    ),
    path(
        'building-notices/<uuid:notice_id>/acknowledge/',
        BuildingNoticeAckView.as_view(),
        name='building-notice-ack',
    ),
    path('floors/<uuid:pk>/', FloorDetailView.as_view(), name='floor-detail'),
    path('floors/<uuid:pk>/stats/', FloorStatsView.as_view(), name='floor-stats'),
    path('flats/', FlatListCreateView.as_view(), name='flat-list'),
    path('flats/<uuid:pk>/', FlatDetailView.as_view(), name='flat-detail'),
    path(
        'flats/<uuid:pk>/assign-renter/',
        FlatAssignRenterView.as_view(),
        name='flat-assign-renter',
    ),
    path(
        'flats/<uuid:pk>/ensure-listing/',
        FlatEnsureListingView.as_view(),
        name='flat-ensure-listing',
    ),
    path('flats/<uuid:pk>/vacate/', FlatVacateView.as_view(), name='flat-vacate'),
    path('tenancies/mine/', MyTenanciesView.as_view(), name='tenancies-mine'),
    path('renters/', RenterListView.as_view(), name='renter-list'),
    path(
        'renters/<uuid:pk>/history/',
        RenterHistoryView.as_view(),
        name='renter-history',
    ),
    path('portfolio/snapshot/', PortfolioSnapshotView.as_view(), name='portfolio-snapshot'),
]
