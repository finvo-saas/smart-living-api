from django.urls import path

from subscriptions.views import (
    FeaturedBoostOptionsView,
    FeaturedBoostView,
    FlatLimitStatusView,
    OwnerSubscriptionView,
    UpgradeSubscriptionView,
)

urlpatterns = [
    path('subscriptions/mine/', OwnerSubscriptionView.as_view(), name='subscription-mine'),
    path(
        'subscriptions/flat-limit/',
        FlatLimitStatusView.as_view(),
        name='subscription-flat-limit',
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
]
