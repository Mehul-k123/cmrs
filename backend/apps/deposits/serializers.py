from decimal import Decimal

from rest_framework import serializers

from apps.cash.serializers import SubmissionSerializer

from .models import BankDeposit

money = {"max_digits": 14, "decimal_places": 2}


class DepositSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True)
    settled_by_name = serializers.CharField(source="settled_by.display_name", read_only=True, default=None)
    is_delayed = serializers.BooleanField(read_only=True, default=False)
    deposit_difference = serializers.SerializerMethodField()
    settlement_difference = serializers.SerializerMethodField()

    class Meta:
        model = BankDeposit
        fields = ["id", "deposit_number", "branch", "branch_name", "bank_name", "account_number",
                  "reference_number", "deposit_date", "reconciled_amount", "amount", "deposit_difference",
                  "status", "mismatch_reason", "created_by_name", "created_at", "settled_amount", "settled_on",
                  "settlement_reference", "settled_by_name", "settlement_difference", "failure_reason",
                  "is_delayed", "delay_flagged_at"]
        read_only_fields = fields

    def get_deposit_difference(self, obj) -> str:
        return str(obj.reconciled_amount - obj.amount)

    def get_settlement_difference(self, obj) -> str | None:
        return None if obj.settled_amount is None else str(obj.amount - obj.settled_amount)


class DepositDetailSerializer(DepositSerializer):
    submissions = SubmissionSerializer(many=True, read_only=True)

    class Meta(DepositSerializer.Meta):
        fields = DepositSerializer.Meta.fields + ["submissions"]
        read_only_fields = fields


class DepositCreateSerializer(serializers.Serializer):
    branch = serializers.IntegerField(required=False, help_text="Defaults to the user's branch")
    submission_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    bank_name = serializers.CharField(max_length=80)
    account_number = serializers.CharField(max_length=30)
    reference_number = serializers.CharField(max_length=60)
    deposit_date = serializers.DateField()
    amount = serializers.DecimalField(**money, min_value=Decimal("0.01"))
    mismatch_reason = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class SettleSerializer(serializers.Serializer):
    settled_amount = serializers.DecimalField(**money, min_value=Decimal("0"))
    settled_on = serializers.DateField()
    settlement_reference = serializers.CharField(max_length=60)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class FailSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
