"""Reusable request pagination helpers for APIView list endpoints."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from django.core.paginator import EmptyPage, Paginator
from django.db.models import QuerySet
from rest_framework.request import Request
from rest_framework.response import Response

from core.envelope import api_success


def parse_page_params(request: Request, *, default_size: int = 20, max_size: int = 100):
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size', str(default_size)))
    except (TypeError, ValueError):
        page_size = default_size
    page_size = max(1, min(page_size, max_size))
    return page, page_size


def search_term(request: Request, *, min_chars: int = 3) -> str:
    """Return trimmed search only when it meets the minimum length."""
    raw = (request.query_params.get('search') or '').strip()
    if len(raw) < min_chars:
        return ''
    return raw


def query_flag(request: Request, key: str) -> str:
    value = (request.query_params.get(key) or '').strip()
    if not value or value.lower() in ('all', '*'):
        return ''
    return value


def paginated_response(
    request: Request,
    source: QuerySet | Sequence[Any],
    *,
    serialize_page: Callable[[Sequence[Any]], list],
    default_size: int = 20,
    max_size: int = 100,
) -> Response:
    """
    Paginate a queryset or in-memory sequence and return the standard envelope:

        { ok, data: { results, count, page, pageSize, totalPages, next, previous } }
    """
    page, page_size = parse_page_params(
        request,
        default_size=default_size,
        max_size=max_size,
    )
    paginator = Paginator(source, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    results = serialize_page(list(page_obj.object_list))
    total_pages = paginator.num_pages or 1
    current = page_obj.number

    def _page_url(target: int | None) -> str | None:
        if target is None or target < 1 or target > total_pages:
            return None
        query = request.query_params.copy()
        query['page'] = str(target)
        query['page_size'] = str(page_size)
        return request.build_absolute_uri(f'?{query.urlencode()}')

    return Response(
        api_success(
            {
                'results': results,
                'count': paginator.count,
                'page': current,
                'pageSize': page_size,
                'totalPages': total_pages,
                'next': _page_url(current + 1) if page_obj.has_next() else None,
                'previous': _page_url(current - 1) if page_obj.has_previous() else None,
            },
        ),
    )
