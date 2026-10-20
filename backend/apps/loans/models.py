from django.conf import settings
from django.db import models
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.fields import MoneyField
from apps.core.models import TimeStampedModel
from apps.core.money import ZERO, to_money


class Customer(TimeStampedModel):
    customer_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="customers")
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="assigned_customers", limit_choices_to={"role": "AGENT"},
    )

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["branch", "assigned_agent"])]

    def __str__(self):
        return f"{self.customer_code} {self.name}"


_money0 = Value(ZERO, output_field=DecimalField(max_digits=14, decimal_places=2))


class LoanQuerySet(models.QuerySet):
    def with_totals(self):
        return self.annotate(
            total_due=Coalesce(Sum("installments__amount_due"), _money0),
            total_paid=Coalesce(Sum("installments__amount_paid"), _money0),
        ).annotate(outstanding=F("total_due") - F("total_paid"))


class Loan(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    loan_number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="loans")
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="loans")
    principal = MoneyField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Flat annual rate, %")
    tenure_months = models.PositiveSmallIntegerField()
    disbursed_on = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    objects = LoanQuerySet.as_manager()

    class Meta:
        ordering = ["-disbursed_on", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(principal__gt=0), name="loan_principal_positive"),
            models.CheckConstraint(condition=Q(tenure_months__gt=0), name="loan_tenure_positive"),
            models.CheckConstraint(condition=Q(interest_rate__gte=0), name="loan_rate_non_negative"),
        ]

    def __str__(self):
        return self.loan_number

    def compute_totals(self) -> dict:
        agg = self.installments.aggregate(due=Sum("amount_due"), paid=Sum("amount_paid"))
        due, paid = to_money(agg["due"]), to_money(agg["paid"])
        return {"total_due": due, "total_paid": paid, "outstanding": to_money(due - paid)}


class RepaymentInstallment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIAL = "PARTIAL", "Partially paid"
        PAID = "PAID", "Paid"

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="installments")
    number = models.PositiveSmallIntegerField()
    due_date = models.DateField(db_index=True)
    amount_due = MoneyField()
    amount_paid = MoneyField(default=ZERO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["loan", "number"]
        constraints = [
            models.UniqueConstraint(fields=["loan", "number"], name="uniq_installment_number"),
            models.CheckConstraint(condition=Q(amount_due__gt=0), name="installment_due_positive"),
            models.CheckConstraint(
                condition=Q(amount_paid__gte=0) & Q(amount_paid__lte=F("amount_due")),
                name="installment_paid_within_due",
            ),
        ]

    def __str__(self):
        return f"{self.loan.loan_number} #{self.number}"

    @property
    def balance(self):
        return to_money(self.amount_due - self.amount_paid)

    @property
    def is_overdue(self):
        return self.status != self.Status.PAID and self.due_date < timezone.localdate()

    def refresh_status(self):
        if self.amount_paid <= ZERO:
            self.status = self.Status.PENDING
        elif self.amount_paid >= self.amount_due:
            self.status = self.Status.PAID
        else:
            self.status = self.Status.PARTIAL
