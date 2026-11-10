"""Pagination for the list endpoints."""

from rest_framework import pagination


class PageNumberPagination(pagination.PageNumberPagination):
    """Pages of 50 records; ``?page_size=`` asks for up to 1000 records on a page."""

    page_size_query_param = "page_size"
    max_page_size = 1000
