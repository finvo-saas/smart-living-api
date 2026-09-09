from django.urls import path

from subscriptions.views import (
    AdCampaignAnalyticsView,
    AdCampaignDetailView,
    AdCampaignListCreateView,
    FeaturedBoostOptionsView,
    FeaturedBoostView,
    FlatLimitStatusView,
    OwnerSubscriptionView,
    OwnerUsageStatusView,
    SubscriptionPlansView,
    UpgradeSubscriptionView,
)

urlpatterns = [
    path('subscriptions/mine/', OwnerSubscriptionView.as_view(), name='subscription-mine'),
    path(
        'subscriptions/plans/',
        SubscriptionPlansView.as_view(),
        name='subscription-plans',
    ),
    path(
        'subscriptions/flat-limit/',
        FlatLimitStatusView.as_view(),
        name='subscription-flat-limit',
    ),
    path(
        'subscriptions/usage/',
        OwnerUsageStatusView.as_view(),
        name='subscription-usage',
    ),
    path(
        'subscriptions/upgrade/',
        UpgradeSubscriptionView.as_view(),
        name='subscription-upgrade',
    ),
    path(
        'subscriptions/featured-boost/',
        FeaturedBoostView.as_view(),
        name='subscription-featured-boost',
    ),
    path(
        'subscriptions/featured-boost/options/',
        FeaturedBoostOptionsView.as_view(),
        name='subscription-featured-boost-options',
    ),
    path(
        'subscriptions/campaigns/',
        AdCampaignListCreateView.as_view(),
        name='ad-campaigns',
    ),
    path(
        'subscriptions/campaigns/analytics/',
        AdCampaignAnalyticsView.as_view(),
        name='ad-campaign-analytics',
    ),
    path(
        'subscriptions/campaigns/<uuid:pk>/',
        AdCampaignDetailView.as_view(),
        name='ad-campaign-detail',
    ),
]
