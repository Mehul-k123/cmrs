import django_filters
from rest_framework import viewsets

from .models import AuditLog, Branch
from .permissions import ReadOnlyOrRoles, Role, has_role
from .serializers import AuditLogSerializer, BranchSerializer


class BranchViewSet(viewsets.ModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [ReadOnlyOrRoles]
    write_roles = (Role.ADMIN,)
    http_method_names = ["get", "post", "patch", "head", "options"]
    search_fields = ["code", "name"]

    def get_queryset(self):
        user = self.request.user
        qs = Branch.objects.all()
        if getattr(user, "role", None) in Role.ORG_WIDE:
            return qs
        return qs.filter(pk=getattr(user, "branch_id", None))


class AuditLogFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["action", "entity_type", "entity_id", "actor"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [has_role(Role.ADMIN, Role.FINANCE)]
    filterset_class = AuditLogFilter
    queryset = AuditLog.objects.select_related("actor")
