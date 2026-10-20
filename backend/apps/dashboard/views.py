from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BusinessRuleError

from .services import DashboardFilters, build_summary


class DashboardSummaryView(APIView):
    @extend_schema(
        parameters=[OpenApiParameter(n, str) for n in ("date_from", "date_to", "branch", "agent", "status")],
        responses={200: dict},
    )
    def get(self, request):
        try:
            filters = DashboardFilters.from_request(request)
        except ValueError as exc:
            raise BusinessRuleError("Invalid filter value.", code="invalid_filter") from exc
        if filters.date_from > filters.date_to:
            raise BusinessRuleError("date_from must be on or before date_to.", code="invalid_filter")
        if (filters.date_to - filters.date_from).days > 366:
            raise BusinessRuleError("Date range cannot exceed one year.", code="invalid_filter")
        return Response(build_summary(filters))
