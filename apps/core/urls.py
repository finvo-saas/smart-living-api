from django.urls import include, path

from core.views import HealthCheckView, MediaUploadView

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health'),
    path('media/upload/', MediaUploadView.as_view(), name='media-upload'),
    path('', include('accounts.urls')),
    path('', include('listings.urls')),
    path('', include('discovery.urls')),
    path('', include('portfolio.urls')),
    path('', include('billing.urls')),
    path('', include('subscriptions.urls')),
    path('', include('payments.urls')),
    path('', include('bookings.urls')),
    path('', include('hotels.urls')),
    path('', include('mess.urls')),
    path('', include('ops.urls')),
    path('', include('support.urls')),
    path('', include('messaging.urls')),
    path('', include('documents.urls')),
    path('', include('reports.urls')),
    path('', include('audit.urls')),
    path('', include('admin_api.urls')),
]
