from decimal import Decimal

from rest_framework import serializers

from .models import PaymentIntent


class PaymentIntentSerializer(serializers.ModelSerializer):
    loan_number = serializers.CharField(source="loan.loan_number", read_only=True)
    customer_name = serializers.CharField(source="loan.customer.name", read_only=True)
    receipt_number = serializers.CharField(source="collection.receipt_number", read_only=True, default=None)

    class Meta:
        model = PaymentIntent
        fields = ["id", "intent_number", "gateway_ref", "loan", "loan_number", "customer_name", "amount", "status",
                  "receipt_number", "failure_reason", "paid_at", "settled_at", "created_at"]
        read_only_fields = fields


class IntentCreateSerializer(serializers.Serializer):
    loan = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))


class SimulateSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(choices=["success", "failure"])
