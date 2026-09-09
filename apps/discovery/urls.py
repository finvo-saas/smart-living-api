from django.urls import path

from discovery.views import (
    DiscoverConfirmView,
    DiscoverFeedView,
    DiscoverReportView,
    DiscoverSearchView,
    HeartbeatPublicView,
    FavoriteCheckView,
    FavoriteListView,
    FavoriteToggleView,
    SavedSearchDetailView,
    SavedSearchListCreateView,
    SearchHistoryClearView,
    SearchHistoryDetailView,
    SearchHistoryListCreateView,
    SearchNotificationsView,
)
from discovery.views_p1 import AreaCompareView, AreaListView, NearbyPOIView
from discovery.views_p2 import UniversityDetailView, UniversityListView
from discovery.views_seo import (
    AreaSeoDetailView,
    AreaSeoListView,
    GeocodeView,
    SitemapDataView,
)

urlpatterns = [
    path('discover/', DiscoverFeedView.as_view(), name='discover-feed'),
    path('discover/search/', DiscoverSearchView.as_view(), name='discover-search'),
    path('discover/pois/', NearbyPOIView.as_view(), name='discover-pois'),
    path('discover/geocode/', GeocodeView.as_view(), name='discover-geocode'),
    path('discover/areas/', AreaListView.as_view(), name='discover-areas'),
    path(
        'discover/areas/compare/',
        AreaCompareView.as_view(),
        name='discover-areas-compare',
    ),
    path('seo/sitemap/', SitemapDataView.as_view(), name='seo-sitemap'),
    path('areas/seo/', AreaSeoListView.as_view(), name='areas-seo-list'),
    path(
        'areas/seo/<slug:city_slug>/<slug:area_slug>/',
        AreaSeoDetailView.as_view(),
        name='areas-seo-detail',
    ),
    path('universities/', UniversityListView.as_view(), name='universities'),
    path(
        'universities/<slug:slug>/',
        UniversityDetailView.as_view(),
        name='university-detail',
    ),
    path('discover/confirm/', DiscoverConfirmView.as_view(), name='discover-confirm'),
    path('discover/report/', DiscoverReportView.as_view(), name='discover-report'),
    path(
        'heartbeat/<str:token>/',
        HeartbeatPublicView.as_view(),
        name='heartbeat-public',
    ),
    path('favorites/', FavoriteListView.as_view(), name='favorites'),
    path('favorites/toggle/', FavoriteToggleView.as_view(), name='favorites-toggle'),
    path('favorites/check/', FavoriteCheckView.as_view(), name='favorites-check'),
    path('saved-searches/', SavedSearchListCreateView.as_view(), name='saved-searches'),
    path(
        'saved-searches/<uuid:pk>/',
        SavedSearchDetailView.as_view(),
        name='saved-search-detail',
    ),
    path('search-history/', SearchHistoryListCreateView.as_view(), name='search-history'),
    path(
        'search-history/clear/',
        SearchHistoryClearView.as_view(),
        name='search-history-clear',
    ),
    path(
        'search-history/<uuid:pk>/',
        SearchHistoryDetailView.as_view(),
        name='search-history-detail',
    ),
    path(
        'search/notifications/',
        SearchNotificationsView.as_view(),
        name='search-notifications',
    ),
]
