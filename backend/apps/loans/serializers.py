from datetime import date

from rest_framework import serializers

from apps.accounts.models import User
from apps.core.permissions import Role

from .models import Customer, Loan, RepaymentInstallment


class CustomerSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    assigned_agent_name = serializers.CharField(source="assigned_agent.display_name", read_only=True, default=None)
    active_loans = serializers.IntegerField(read_only=True, default=0)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, default=None)

    class Meta:
        model = Customer
        fields = ["id", "customer_code", "name", "phone", "address", "branch", "branch_name",
                  "assigned_agent", "assigned_agent_name", "active_loans", "outstanding", "created_at"]
        read_only_fields = ["customer_code"]

    def validate(self, attrs):
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        agent: User | None = attrs.get("assigned_agent", getattr(self.instance, "assigned_agent", None))
        if agent and (agent.role != Role.AGENT or agent.branch_id != getattr(branch, "id", None)):
            raise serializers.ValidationError(
                {"assigned_agent": "Assigned agent must be a collection agent of the same branch."}
            )
        return attrs


class InstallmentSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = RepaymentInstallment
        fields = ["id", "number", "due_date", "amount_due", "amount_paid", "balance", "status", "is_overdue"]


class LoanSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_code = serializers.CharField(source="customer.customer_code", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    total_due = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    next_due_date = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = ["id", "loan_number", "customer", "customer_name", "customer_code", "branch", "branch_name",
                  "principal", "interest_rate", "tenure_months", "disbursed_on", "status",
                  "total_due", "total_paid", "outstanding", "next_due_date", "created_at"]
        read_only_fields = ["loan_number", "branch", "status"]

    def get_next_due_date(self, obj) -> date | None:
        nxt = next((i for i in obj.installments.all() if i.status != "PAID"), None)
        return nxt.due_date if nxt else None


class LoanCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.select_related("branch"))
    principal = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=60)
    tenure_months = serializers.IntegerField(min_value=1, max_value=120)
    disbursed_on = serializers.DateField()
    first_due_date = serializers.DateField(required=False)
