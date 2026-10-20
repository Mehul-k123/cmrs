import django_filters
from django.db.models import Count, Prefetch, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.permissions import ReadOnlyOrRoles, Role, scope_queryset
from apps.core.sequences import make_reference

from .models import Customer, Loan, RepaymentInstallment
from .serializers import CustomerSerializer, InstallmentSerializer, LoanCreateSerializer, LoanSerializer
from .services import create_loan


class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [ReadOnlyOrRoles]
    write_roles = (Role.ADMIN, Role.BRANCH_MANAGER)
    filterset_fields = ["branch", "assigned_agent"]
    search_fields = ["name", "customer_code", "phone"]
    ordering_fields = ["name", "created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Customer.objects.select_related("branch", "assigned_agent").annotate(
            active_loans=Count("loans", filter=Q(loans__status=Loan.Status.ACTIVE))
        ).order_by("name")
        return scope_queryset(qs, self.request.user, agent_field="assigned_agent")

    def _check_branch(self, serializer):
        user = self.request.user
        branch = serializer.validated_data.get("branch", getattr(serializer.instance, "branch", None))
        if user.role == Role.BRANCH_MANAGER and branch and branch.id != user.branch_id:
            raise BusinessRuleError("You can only manage customers of your branch.", code="forbidden_branch",
                                    status_code=403)

    def perform_create(self, serializer):
        self._check_branch(serializer)
        branch = serializer.validated_data["branch"]
        serializer.save(customer_code=make_reference("CUST", branch.code))

    def perform_update(self, serializer):
        self._check_branch(serializer)
        serializer.save()


class LoanFilter(django_filters.FilterSet):
    agent = django_filters.NumberFilter(field_name="customer__assigned_agent")

    class Meta:
        model = Loan
        fields = ["customer", "branch", "status", "agent"]


class LoanViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = LoanSerializer
    permission_classes = [ReadOnlyOrRoles]
    write_roles = (Role.ADMIN, Role.BRANCH_MANAGER)
    filterset_class = LoanFilter
    search_fields = ["loan_number", "customer__name", "customer__customer_code"]
    ordering_fields = ["disbursed_on", "principal"]

    def get_queryset(self):
        qs = (
            Loan.objects.with_totals()
            .select_related("customer", "branch")
            .prefetch_related(Prefetch("installments", queryset=RepaymentInstallment.objects.order_by("number")))
        )
        return scope_queryset(qs, self.request.user, agent_field="customer__assigned_agent")

    @extend_schema(request=LoanCreateSerializer, responses=LoanSerializer)
    def create(self, request, *args, **kwargs):
        ser = LoanCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        customer = ser.validated_data["customer"]
        user = request.user
        if user.role == Role.BRANCH_MANAGER and customer.branch_id != user.branch_id:
            raise BusinessRuleError("Customer belongs to another branch.", code="forbidden_branch", status_code=403)
        loan = create_loan(actor=user, **ser.validated_data)
        return Response(LoanSerializer(self.get_queryset().get(pk=loan.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=InstallmentSerializer(many=True))
    @action(detail=True)
    def schedule(self, request, pk=None):
        loan = self.get_object()
        return Response(InstallmentSerializer(loan.installments.all(), many=True).data)

    @action(detail=True)
    def repayments(self, request, pk=None):
        from apps.cash.serializers import CollectionSerializer

        loan = self.get_object()
        qs = loan.collections.select_related("agent", "customer", "loan", "branch").order_by("-collected_at")
        return Response(CollectionSerializer(qs, many=True).data)
