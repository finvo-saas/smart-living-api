from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from core.envelope import api_error, api_success


class EnvelopeAPIException(APIException):
    """DRF exception with an ApiResult error code."""

    default_code = 'UNKNOWN'
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        if code is not None:
            self.default_code = code
        self.detail = detail
        super().__init__(detail=detail, code=code)


class NotFoundError(EnvelopeAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found.'
    default_code = 'NOT_FOUND'


class ForbiddenError(EnvelopeAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Permission denied.'
    default_code = 'FORBIDDEN'


class InvalidError(EnvelopeAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid request.'
    default_code = 'INVALID'


class InvalidAccountError(EnvelopeAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid account.'
    default_code = 'INVALID_ACCOUNT'


class GatewayTodoError(EnvelopeAPIException):
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    default_detail = 'Payment gateway not configured.'
    default_code = 'GATEWAY_TODO'


class ConflictError(EnvelopeAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Resource conflict.'
    default_code = 'CONFLICT'


class UnavailableError(EnvelopeAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Resource unavailable.'
    default_code = 'UNAVAILABLE'


class UnpublishedError(EnvelopeAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Listing is not published.'
    default_code = 'UNPUBLISHED'


class InvalidStateError(EnvelopeAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid state transition.'
    default_code = 'INVALID_STATE'


class ReasonRequiredError(EnvelopeAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Reason is required.'
    default_code = 'REASON_REQUIRED'


def envelope_exception_handler(exc, context):
    from rest_framework.views import exception_handler

    response = exception_handler(exc, context)

    if response is not None:
        code = getattr(exc, 'default_code', 'UNKNOWN')
        if hasattr(exc, 'get_codes'):
            codes = exc.get_codes()
            if isinstance(codes, str):
                code = codes.upper() if codes.islower() else codes
            elif isinstance(codes, dict):
                code = 'INVALID'

        if isinstance(exc, EnvelopeAPIException):
            code = exc.default_code

        detail = response.data
        if isinstance(detail, dict):
            if 'detail' in detail:
                message = str(detail['detail'])
            else:
                message = '; '.join(
                    f'{k}: {v}' if not isinstance(v, list) else f'{k}: {", ".join(str(i) for i in v)}'
                    for k, v in detail.items()
                )
        elif isinstance(detail, list):
            message = '; '.join(str(item) for item in detail)
        else:
            message = str(detail)

        return Response(
            api_error(message, code=code),
            status=response.status_code,
        )

    return Response(
        api_error('An unexpected error occurred.', code='UNKNOWN'),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
