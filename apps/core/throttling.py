"""DRF throttle classes with optional disable via settings."""

from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


def client_ip(request) -> str:
    """Real visitor IP behind Cloudflare + nginx.

    Every browser request arrives from the nginx container. Without this, all
    visitors share one hourly bucket and the site looks empty after a few pages.
    """
    forwarded = (request.META.get('HTTP_CF_CONNECTING_IP') or '').split(',')[0].strip()
    if forwarded:
        return forwarded
    return SimpleRateThrottle.get_ident(request)


class ConfigurableAnonRateThrottle(AnonRateThrottle):
    def get_ident(self, request):
        return client_ip(request)

    def allow_request(self, request, view):
        if not getattr(settings, 'API_THROTTLING_ENABLED', False):
            return True
        return super().allow_request(request, view)


class ConfigurableUserRateThrottle(UserRateThrottle):
    def get_ident(self, request):
        return client_ip(request)

    def allow_request(self, request, view):
        if not getattr(settings, 'API_THROTTLING_ENABLED', False):
            return True
        return super().allow_request(request, view)


class OTPRateThrottle(SimpleRateThrottle):
    """Phone-scoped OTP request throttle (5/hour when enabled)."""

    scope = 'otp'

    def get_cache_key(self, request, view):
        phone = ''
        if hasattr(request, 'data'):
            phone = str(request.data.get('phone') or '')
        ident = phone or client_ip(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}

    def allow_request(self, request, view):
        if not getattr(settings, 'API_THROTTLING_ENABLED', False):
            return True
        return super().allow_request(request, view)
