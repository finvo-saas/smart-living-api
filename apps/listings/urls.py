from django.urls import path

from listings.views import (
    AIMatchView,
    FeaturedPropertiesView,
    OwnerListingsView,
    PropertyBatchView,
    PropertyDetailView,
    PropertyListCreateView,
    PropertyMediaUploadView,
    PropertyMetaView,
    PropertyRecommendationsView,
    PropertyReviewListCreateView,
    PropertyReviewRespondView,
    PropertyReviewSummaryView,
)

urlpatterns = [
    path('properties/', PropertyListCreateView.as_view(), name='property-list'),
    path('properties/featured/', FeaturedPropertiesView.as_view(), name='property-featured'),
    path('properties/meta/', PropertyMetaView.as_view(), name='property-meta'),
    path('properties/mine/', OwnerListingsView.as_view(), name='property-mine'),
    path('properties/batch/', PropertyBatchView.as_view(), name='property-batch'),
    path('properties/ai-match/', AIMatchView.as_view(), name='property-ai-match'),
    path(
        'properties/<uuid:pk>/',
        PropertyDetailView.as_view(),
        name='property-detail',
    ),
    path(
        'properties/<uuid:pk>/media/',
        PropertyMediaUploadView.as_view(),
        name='property-media',
    ),
    path(
        'properties/<uuid:pk>/recommendations/',
        PropertyRecommendationsView.as_view(),
        name='property-recommendations',
    ),
    path(
        'properties/<uuid:pk>/reviews/',
        PropertyReviewListCreateView.as_view(),
        name='property-reviews',
    ),
    path(
        'properties/<uuid:pk>/reviews/summary/',
        PropertyReviewSummaryView.as_view(),
        name='property-review-summary',
    ),
    path(
        'properties/<uuid:pk>/reviews/<uuid:review_id>/respond/',
        PropertyReviewRespondView.as_view(),
        name='property-review-respond',
    ),
]
