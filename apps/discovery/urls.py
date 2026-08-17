from django.urls import path

from discovery.views import (
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

urlpatterns = [
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
