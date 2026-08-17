"""DRF throttle classes with optional disable via settings."""

from django.conf import settings
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class ConfigurableAnonRateThrottle(AnonRateThrottle):
    def allow_request(self, request, view):
        if not getattr(settings, 'API_THROTTLING_ENABLED', False):
            return True
        return super().allow_request(request, view)


class ConfigurableUserRateThrottle(UserRateThrottle):
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
        if not phone:
            return self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': phone}

    def allow_request(self, request, view):
        if not getattr(settings, 'API_THROTTLING_ENABLED', False):
            return True
        return super().allow_request(request, view)
