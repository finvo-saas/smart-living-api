"""httpOnly auth cookies (refresh JWT + trusted device)."""

from django.conf import settings


def refresh_cookie_name() -> str:
    return getattr(settings, 'AUTH_REFRESH_COOKIE_NAME', 'sl_refresh')


def device_cookie_name() -> str:
    return getattr(settings, 'AUTH_DEVICE_COOKIE_NAME', 'sl_device')


def _cookie_path() -> str:
    return getattr(settings, 'AUTH_COOKIE_PATH', '/api/v1/auth/')


def _samesite() -> str:
    value = getattr(settings, 'AUTH_COOKIE_SAMESITE', 'Lax') or 'Lax'
    if str(value).lower() == 'none':
        return 'None'
    return value


def _secure() -> bool:
    samesite = _samesite()
    if samesite == 'None':
        return True
    return bool(getattr(settings, 'AUTH_COOKIE_SECURE', not settings.DEBUG))


def _domain() -> str | None:
    domain = (getattr(settings, 'AUTH_COOKIE_DOMAIN', None) or '').strip()
    return domain or None


def _kwargs(*, max_age: int) -> dict:
    kwargs = {
        'httponly': True,
        'secure': _secure(),
        'samesite': _samesite(),
        'path': _cookie_path(),
        'max_age': max_age,
    }
    domain = _domain()
    if domain:
        kwargs['domain'] = domain
    return kwargs


def set_refresh_cookie(response, refresh: str) -> None:
    lifetime = settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
    max_age = int(lifetime.total_seconds())
    response.set_cookie(refresh_cookie_name(), refresh, **_kwargs(max_age=max_age))


def clear_refresh_cookie(response) -> None:
    response.delete_cookie(
        refresh_cookie_name(),
        path=_cookie_path(),
        domain=_domain(),
        samesite=_samesite(),
    )


def set_device_cookie(response, token: str) -> None:
    days = int(getattr(settings, 'AUTH_DEVICE_TTL_DAYS', 90))
    response.set_cookie(
        device_cookie_name(),
        token,
        **_kwargs(max_age=days * 86400),
    )


def clear_device_cookie(response) -> None:
    response.delete_cookie(
        device_cookie_name(),
        path=_cookie_path(),
        domain=_domain(),
        samesite=_samesite(),
    )


def read_refresh_token(request) -> str:
    cookie = request.COOKIES.get(refresh_cookie_name()) or ''
    if cookie:
        return cookie
    data = getattr(request, 'data', None) or {}
    return str(data.get('refresh') or '')
