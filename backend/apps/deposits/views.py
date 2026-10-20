import django_filters
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import BusinessRuleError
from apps.core.filters import DateRangeFilterSet
from apps.core.models import Branch
from apps.core.permissions import Role, has_role, scope_queryset

from . import services
from .models import BankDeposit
from .serializers import (
    DepositCreateSerializer,
    DepositDetailSerializer,
    DepositSerializer,
    FailSerializer,
    SettleSerializer,
)


class DepositFilter(DateRangeFilterSet):
    date_field = "deposit_date"
    is_datetime = False
    status = django_filters.MultipleChoiceFilter(choices=BankDeposit.Status.choices)
    delayed = django_filters.BooleanFilter(field_name="is_delayed")

    class Meta:
        model = BankDeposit
        fields = ["branch", "status", "bank_name"]


class DepositViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    filterset_class = DepositFilter
    search_fields = ["deposit_number", "reference_number", "bank_name"]
    ordering_fields = ["deposit_date", "amount"]

    def get_permissions(self):
        if self.action == "create":
            return [has_role(Role.BRANCH_MANAGER, Role.ADMIN)()]
        if self.action in ("settle", "fail"):
            return [has_role(Role.FINANCE, Role.ADMIN)()]
        return [has_role(Role.ADMIN, Role.FINANCE, Role.BRANCH_MANAGER)()]

    def get_queryset(self):
        qs = BankDeposit.objects.with_delay_flag().select_related("branch", "created_by", "settled_by")
        if self.action == "retrieve":
            qs = qs.prefetch_related("submissions__agent", "submissions__branch")
        return scope_queryset(qs, self.request.user)

    def get_serializer_class(self):
        return DepositDetailSerializer if self.action == "retrieve" else DepositSerializer

    def _detail(self, deposit, code=status.HTTP_200_OK):
        return Response(DepositDetailSerializer(self.get_queryset().get(pk=deposit.pk)).data, status=code)

    @extend_schema(request=DepositCreateSerializer, responses={201: DepositDetailSerializer})
    def create(self, request, *args, **kwargs):
        ser = DepositCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        branch_id = data.pop("branch", None) or request.user.branch_id
        if not branch_id:
            raise BusinessRuleError("Branch is required.", code="branch_required")
        branch = get_object_or_404(Branch, pk=branch_id)
        deposit = services.create_deposit(actor=request.user, branch=branch, **data)
        return self._detail(deposit, status.HTTP_201_CREATED)

    @extend_schema(request=SettleSerializer, responses=DepositDetailSerializer)
    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        deposit = self.get_object()
        ser = SettleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        deposit = services.settle_deposit(actor=request.user, deposit_id=deposit.pk, **ser.validated_data)
        return self._detail(deposit)

    @extend_schema(request=FailSerializer, responses=DepositDetailSerializer)
    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        deposit = self.get_object()
        ser = FailSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        deposit = services.fail_deposit(actor=request.user, deposit_id=deposit.pk, reason=ser.validated_data["reason"])
        return self._detail(deposit)
