"""ApiResult envelope helpers — matches frontend lib/api/http.ts."""

from typing import Any


def api_success(data: Any = None) -> dict:
    return {'ok': True, 'data': data}


def api_error(message: str, code: str = 'UNKNOWN') -> dict:
    return {'ok': False, 'error': message, 'code': code}
