from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.envelope import api_success


class EnvelopePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_page_size(self, request):
        from django.conf import settings

        self.page_size = getattr(settings, 'API_PAGE_SIZE', self.page_size)
        return super().get_page_size(request)

    def get_paginated_response(self, data):
        return Response(
            api_success(
                {
                    'results': data,
                    'count': self.page.paginator.count,
                    'next': self.get_next_link(),
                    'previous': self.get_previous_link(),
                },
            ),
        )
