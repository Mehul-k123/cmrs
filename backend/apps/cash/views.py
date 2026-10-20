import django_filters
from django.db.models import Count, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.filters import DateRangeFilterSet
from apps.core.money import to_money
from apps.core.permissions import Role, has_role, scope_queryset

from . import services
from .models import CashSubmission, Collection, Discrepancy
from .serializers import (
    ApproveSerializer,
    CollectionCreateSerializer,
    CollectionDetailSerializer,
    CollectionSerializer,
    DiscrepancySerializer,
    ReasonSerializer,
    ResolveSerializer,
    SubmissionCreateSerializer,
    SubmissionDetailSerializer,
    SubmissionSerializer,
)

ALL_ROLES = (Role.ADMIN, Role.FINANCE, Role.BRANCH_MANAGER, Role.AGENT)


class CollectionFilter(DateRangeFilterSet):
    date_field = "collected_at"
    status = django_filters.MultipleChoiceFilter(choices=Collection.Status.choices)

    class Meta:
        model = Collection
        fields = ["branch", "agent", "loan", "customer", "mode", "status"]


class CollectionViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    """Collections are append-only: there is deliberately no update or delete endpoint."""

    filterset_class = CollectionFilter
    search_fields = ["receipt_number", "customer__name", "loan__loan_number"]
    ordering_fields = ["collected_at", "amount"]

    def get_permissions(self):
        if self.action == "create":
            return [has_role(Role.AGENT)()]
        if self.action == "reverse":
            return [has_role(Role.ADMIN, Role.BRANCH_MANAGER)()]
        return [has_role(*ALL_ROLES)()]

    def get_queryset(self):
        qs = Collection.objects.select_related("loan", "customer", "agent", "branch")
        if self.action == "retrieve":
            qs = qs.prefetch_related("allocations__installment")
        return scope_queryset(qs, self.request.user, agent_field="agent")

    def get_serializer_class(self):
        return CollectionDetailSerializer if self.action == "retrieve" else CollectionSerializer

    @extend_schema(
        request=CollectionCreateSerializer,
        responses={201: CollectionDetailSerializer, 200: CollectionDetailSerializer},
        parameters=[OpenApiParameter("Idempotency-Key", str, OpenApiParameter.HEADER, required=True)],
    )
    def create(self, request, *args, **kwargs):
        ser = CollectionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        collection, created = services.record_cash_collection(
            agent=request.user,
            loan_id=d["loan"],
            amount=d["amount"],
            idempotency_key=request.headers.get("Idempotency-Key", "").strip(),
            collected_at=d.get("collected_at"),
            notes=d.get("notes", ""),
            confirm_duplicate=d["confirm_duplicate"],
        )
        return Response(CollectionDetailSerializer(collection).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(parameters=[OpenApiParameter("date", str, description="YYYY-MM-DD, default today")])
    @action(detail=False)
    def daily(self, request):
        """An agent's (or branch's) collections for one day with totals by status."""
        day = request.query_params.get("date") or timezone.localdate().isoformat()
        qs = self.filter_queryset(self.get_queryset()).filter(collected_at__date=day)
        by_status = {r["status"]: {"count": r["n"], "amount": str(to_money(r["total"]))}
                     for r in qs.values("status").annotate(n=Count("id"), total=Sum("amount"))}
        active = qs.exclude(status=Collection.Status.REVERSED)
        total = to_money(active.aggregate(t=Sum("amount"))["t"])
        cash_in_hand = to_money(active.filter(mode=Collection.Mode.CASH, status=Collection.Status.COLLECTED)
                                .aggregate(t=Sum("amount"))["t"])
        return Response({
            "date": day,
            "count": active.count(),
            "total": str(total),
            "cash_in_hand": str(cash_in_hand),
            "by_status": by_status,
            "results": CollectionSerializer(qs, many=True).data,
        })

    @extend_schema(request=ReasonSerializer, responses=CollectionDetailSerializer)
    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        collection = self.get_object()  # enforces scoping
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        collection = services.reverse_collection(actor=request.user, collection_id=collection.pk,
                                                 reason=ser.validated_data["reason"])
        return Response(CollectionDetailSerializer(collection).data)


class SubmissionFilter(DateRangeFilterSet):
    date_field = "submitted_at"
    status = django_filters.MultipleChoiceFilter(choices=CashSubmission.Status.choices)

    class Meta:
        model = CashSubmission
        fields = ["branch", "agent", "status"]


class SubmissionViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    filterset_class = SubmissionFilter
    search_fields = ["submission_number", "agent__username", "agent__first_name"]
    ordering_fields = ["submitted_at", "expected_amount"]

    def get_permissions(self):
        if self.action == "create":
            return [has_role(Role.AGENT)()]
        if self.action in ("approve", "reject"):
            return [has_role(Role.BRANCH_MANAGER, Role.ADMIN)()]
        return [has_role(*ALL_ROLES)()]

    def get_queryset(self):
        qs = CashSubmission.objects.select_related("agent", "branch", "reviewed_by").annotate(
            item_count=Count("items")
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related("items__collection__customer", "items__collection__loan")
        return scope_queryset(qs, self.request.user, agent_field="agent")

    def get_serializer_class(self):
        return SubmissionDetailSerializer if self.action == "retrieve" else SubmissionSerializer

    def _detail(self, submission):
        return Response(SubmissionDetailSerializer(self.get_queryset().get(pk=submission.pk)).data)

    @extend_schema(request=SubmissionCreateSerializer, responses={201: SubmissionDetailSerializer})
    def create(self, request, *args, **kwargs):
        ser = SubmissionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sub = services.create_submission(agent=request.user, collection_ids=ser.validated_data["collection_ids"],
                                         declared_amount=ser.validated_data.get("declared_amount"),
                                         note=ser.validated_data.get("note", ""))
        resp = self._detail(sub)
        resp.status_code = status.HTTP_201_CREATED
        return resp

    @extend_schema(request=ApproveSerializer, responses=SubmissionDetailSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        sub = self.get_object()
        ser = ApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sub = services.approve_submission(reviewer=request.user, submission_id=sub.pk,
                                          received_amount=ser.validated_data["received_amount"],
                                          note=ser.validated_data["note"])
        return self._detail(sub)

    @extend_schema(request=ReasonSerializer, responses=SubmissionDetailSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        sub = self.get_object()
        ser = ReasonSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sub = services.reject_submission(reviewer=request.user, submission_id=sub.pk,
                                         reason=ser.validated_data["reason"])
        return self._detail(sub)


class DiscrepancyFilter(DateRangeFilterSet):
    class Meta:
        model = Discrepancy
        fields = ["branch", "agent", "type", "status"]


class DiscrepancyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DiscrepancySerializer
    filterset_class = DiscrepancyFilter
    permission_classes = [has_role(Role.ADMIN, Role.FINANCE, Role.BRANCH_MANAGER)]

    def get_queryset(self):
        qs = Discrepancy.objects.select_related("branch", "agent", "raised_by", "resolved_by", "submission",
                                                "deposit", "collection")
        return scope_queryset(qs, self.request.user)

    @extend_schema(request=ResolveSerializer, responses=DiscrepancySerializer)
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        d = self.get_object()
        ser = ResolveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = services.resolve_discrepancy(actor=request.user, discrepancy_id=d.pk, note=ser.validated_data["note"])
        return Response(DiscrepancySerializer(d).data)
