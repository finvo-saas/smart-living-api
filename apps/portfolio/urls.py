from django.urls import path

from portfolio.views import (
    BuildingAllListView,
    BuildingDetailView,
    BuildingFlatListView,
    BuildingFloorListCreateView,
    BuildingListCreateView,
    FlatAssignRenterView,
    FlatDetailView,
    FlatListCreateView,
    FlatVacateView,
    FloorDetailView,
    FloorStatsView,
    PortfolioSnapshotView,
    RenterHistoryView,
    RenterListView,
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
    path('floors/<uuid:pk>/', FloorDetailView.as_view(), name='floor-detail'),
    path('floors/<uuid:pk>/stats/', FloorStatsView.as_view(), name='floor-stats'),
    path('flats/', FlatListCreateView.as_view(), name='flat-list'),
    path('flats/<uuid:pk>/', FlatDetailView.as_view(), name='flat-detail'),
    path(
        'flats/<uuid:pk>/assign-renter/',
        FlatAssignRenterView.as_view(),
        name='flat-assign-renter',
    ),
    path('flats/<uuid:pk>/vacate/', FlatVacateView.as_view(), name='flat-vacate'),
    path('renters/', RenterListView.as_view(), name='renter-list'),
    path(
        'renters/<uuid:pk>/history/',
        RenterHistoryView.as_view(),
        name='renter-history',
    ),
    path('portfolio/snapshot/', PortfolioSnapshotView.as_view(), name='portfolio-snapshot'),
]
