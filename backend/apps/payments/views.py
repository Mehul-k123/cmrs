from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import Role, has_role, scope_queryset
from apps.loans.models import Loan

from . import services
from .models import PaymentIntent
from .serializers import IntentCreateSerializer, PaymentIntentSerializer, SimulateSerializer


class PaymentIntentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentIntentSerializer
    filterset_fields = ["loan", "status"]

    def get_permissions(self):
        if self.action == "simulate_settlement":
            return [has_role(Role.FINANCE, Role.ADMIN)()]
        return [has_role(Role.ADMIN, Role.FINANCE, Role.BRANCH_MANAGER, Role.AGENT)()]

    def get_queryset(self):
        qs = PaymentIntent.objects.select_related("loan__customer", "collection")
        return scope_queryset(qs, self.request.user, branch_field="loan__branch",
                              agent_field="loan__customer__assigned_agent")

    @extend_schema(request=IntentCreateSerializer, responses={201: PaymentIntentSerializer})
    def create(self, request):
        ser = IntentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        loans = scope_queryset(Loan.objects.all(), request.user, agent_field="customer__assigned_agent")
        loan = get_object_or_404(loans, pk=ser.validated_data["loan"])
        intent, order = services.create_intent(actor=request.user, loan_id=loan.pk,
                                               amount=ser.validated_data["amount"])
        data = PaymentIntentSerializer(intent).data | {"payment_url": order["payment_url"]}
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(request=SimulateSerializer, responses=PaymentIntentSerializer,
                   description="Mock gateway only: simulate the customer completing or failing the UPI payment.")
    @action(detail=True, methods=["post"])
    def simulate(self, request, pk=None):
        intent = self.get_object()
        ser = SimulateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = services.simulate_payment(intent, ser.validated_data["outcome"] == "success")
        intent.refresh_from_db()
        return Response(PaymentIntentSerializer(intent).data | {"webhook_result": result})

    @extend_schema(request=None, description="Mock gateway only: settle all captured UPI payments.")
    @action(detail=False, methods=["post"], url_path="simulate-settlement")
    def simulate_settlement(self, request):
        return Response(services.simulate_settlement())


class WebhookView(APIView):
    """Gateway → CMRS callback. Authenticated by HMAC signature, not JWT."""

    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(parameters=[OpenApiParameter("X-Signature", str, OpenApiParameter.HEADER, required=True)],
                   request={"application/json": {"type": "object"}}, responses={200: dict})
    def post(self, request):
        result = services.handle_webhook(request.body, request.headers.get("X-Signature", ""))
        return Response(result)
