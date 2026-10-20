from decimal import Decimal

from rest_framework import serializers

from .models import CashSubmission, Collection, CollectionAllocation, Discrepancy, SubmissionItem

money = {"max_digits": 14, "decimal_places": 2}


class AllocationSerializer(serializers.ModelSerializer):
    installment_number = serializers.IntegerField(source="installment.number", read_only=True)
    due_date = serializers.DateField(source="installment.due_date", read_only=True)

    class Meta:
        model = CollectionAllocation
        fields = ["installment_number", "due_date", "amount"]


class CollectionSerializer(serializers.ModelSerializer):
    loan_number = serializers.CharField(source="loan.loan_number", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    agent_name = serializers.CharField(source="agent.display_name", read_only=True, default=None)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Collection
        fields = ["id", "receipt_number", "loan", "loan_number", "customer", "customer_name", "branch",
                  "branch_name", "agent", "agent_name", "amount", "mode", "status", "collected_at",
                  "payment_reference", "notes", "is_locked", "reversed_at", "reversal_reason", "created_at"]
        read_only_fields = fields


class CollectionDetailSerializer(CollectionSerializer):
    allocations = AllocationSerializer(many=True, read_only=True)

    class Meta(CollectionSerializer.Meta):
        fields = CollectionSerializer.Meta.fields + ["allocations"]
        read_only_fields = fields


class CollectionCreateSerializer(serializers.Serializer):
    loan = serializers.IntegerField()
    amount = serializers.DecimalField(**money, min_value=Decimal("0.01"))
    collected_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)
    confirm_duplicate = serializers.BooleanField(default=False)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class SubmissionItemSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(source="collection.receipt_number", read_only=True)
    customer_name = serializers.CharField(source="collection.customer.name", read_only=True)
    loan_number = serializers.CharField(source="collection.loan.loan_number", read_only=True)
    collected_at = serializers.DateTimeField(source="collection.collected_at", read_only=True)

    class Meta:
        model = SubmissionItem
        fields = ["collection", "receipt_number", "customer_name", "loan_number", "collected_at", "amount"]


class SubmissionSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="agent.display_name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.display_name", read_only=True, default=None)
    item_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = CashSubmission
        fields = ["id", "submission_number", "agent", "agent_name", "branch", "branch_name", "expected_amount",
                  "declared_amount", "received_amount", "difference", "status", "submitted_at", "agent_note",
                  "reviewed_by", "reviewed_by_name", "reviewed_at", "review_note", "item_count"]
        read_only_fields = fields


class SubmissionDetailSerializer(SubmissionSerializer):
    items = SubmissionItemSerializer(many=True, read_only=True)

    class Meta(SubmissionSerializer.Meta):
        fields = SubmissionSerializer.Meta.fields + ["items"]
        read_only_fields = fields


class SubmissionCreateSerializer(serializers.Serializer):
    collection_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=500)
    declared_amount = serializers.DecimalField(**money, min_value=Decimal("0"), required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class ApproveSerializer(serializers.Serializer):
    received_amount = serializers.DecimalField(**money, min_value=Decimal("0"))
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class DiscrepancySerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    agent_name = serializers.CharField(source="agent.display_name", read_only=True, default=None)
    raised_by_name = serializers.CharField(source="raised_by.display_name", read_only=True)
    resolved_by_name = serializers.CharField(source="resolved_by.display_name", read_only=True, default=None)
    submission_number = serializers.CharField(source="submission.submission_number", read_only=True, default=None)
    deposit_number = serializers.CharField(source="deposit.deposit_number", read_only=True, default=None)
    receipt_number = serializers.CharField(source="collection.receipt_number", read_only=True, default=None)

    class Meta:
        model = Discrepancy
        fields = ["id", "type", "status", "branch", "branch_name", "agent", "agent_name", "submission",
                  "submission_number", "deposit", "deposit_number", "collection", "receipt_number",
                  "expected_amount", "actual_amount", "difference", "reason", "raised_by_name", "created_at",
                  "resolved_by_name", "resolved_at", "resolution_note"]
        read_only_fields = fields


class ResolveSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=255)
