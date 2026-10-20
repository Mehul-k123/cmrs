from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.fields import MoneyField
from apps.core.models import TimeStampedModel

# Fields that may never change once a collection has been reconciled at the branch.
LOCKED_FIELDS = ("receipt_number", "loan_id", "customer_id", "agent_id", "branch_id", "amount", "mode",
                 "collected_at")


class Collection(TimeStampedModel):
    """A single repayment received from a customer (cash via an agent, or UPI via the gateway)."""

    class Mode(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI / Digital"

    class Status(models.TextChoices):
        COLLECTED = "COLLECTED", "Collected (with agent)"
        SUBMITTED = "SUBMITTED", "Submitted to branch"
        BRANCH_RECEIVED = "BRANCH_RECEIVED", "Received at branch"
        DEPOSITED = "DEPOSITED", "Deposited in bank"
        SETTLED = "SETTLED", "Settled"
        REVERSED = "REVERSED", "Reversed"

    receipt_number = models.CharField(max_length=40, unique=True)
    loan = models.ForeignKey("loans.Loan", on_delete=models.PROTECT, related_name="collections")
    customer = models.ForeignKey("loans.Customer", on_delete=models.PROTECT, related_name="collections")
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="collections")
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="collections"
    )
    amount = MoneyField()
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.CASH)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COLLECTED, db_index=True)
    collected_at = models.DateTimeField(db_index=True)
    idempotency_key = models.CharField(max_length=64, unique=True)
    payment_reference = models.CharField(max_length=64, blank=True, help_text="Gateway reference for UPI")
    notes = models.CharField(max_length=255, blank=True)
    is_locked = models.BooleanField(default=False)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reversal_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-collected_at", "-id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="collection_amount_positive")]
        indexes = [
            models.Index(fields=["agent", "status"]),
            models.Index(fields=["branch", "status"]),
            models.Index(fields=["loan", "collected_at"]),
        ]

    def __str__(self):
        return self.receipt_number

    def save(self, *args, **kwargs):
        # Defence in depth: even code paths that bypass the API cannot alter a reconciled collection.
        if self.pk and self.is_locked:
            original = Collection.objects.filter(pk=self.pk).values(*LOCKED_FIELDS).first()
            if original and any(original[f] != getattr(self, f) for f in LOCKED_FIELDS):
                raise PermissionError(
                    f"Collection {self.receipt_number} is reconciled and its financial fields are locked."
                )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Collections cannot be deleted; reverse them instead.")


class CollectionAllocation(models.Model):
    """How a collection was applied to installments (oldest due first)."""

    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="allocations")
    installment = models.ForeignKey(
        "loans.RepaymentInstallment", on_delete=models.PROTECT, related_name="allocations"
    )
    amount = MoneyField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="allocation_amount_positive")]

    def __str__(self):
        return f"{self.collection_id}->{self.installment_id}: {self.amount}"


class CashSubmission(TimeStampedModel):
    """A batch of cash collections handed over by an agent to their branch."""

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Pending verification"
        APPROVED = "APPROVED", "Approved (at branch)"
        REJECTED = "REJECTED", "Rejected"
        DEPOSITED = "DEPOSITED", "Deposited in bank"
        SETTLED = "SETTLED", "Settled"

    submission_number = models.CharField(max_length=40, unique=True)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submissions")
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="submissions")
    collections = models.ManyToManyField(Collection, through="SubmissionItem", related_name="submissions")
    expected_amount = MoneyField(help_text="Sum of the collections in this submission")
    declared_amount = MoneyField(help_text="Cash the agent says they handed over")
    received_amount = MoneyField(null=True, blank=True, help_text="Cash counted by the branch")
    difference = MoneyField(null=True, blank=True, help_text="expected - received (positive = shortage)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    agent_note = models.CharField(max_length=255, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(expected_amount__gt=0), name="submission_expected_positive"),
            models.CheckConstraint(condition=Q(declared_amount__gte=0), name="submission_declared_non_negative"),
            models.CheckConstraint(
                condition=Q(received_amount__isnull=True) | Q(received_amount__gte=0),
                name="submission_received_non_negative",
            ),
        ]

    def __str__(self):
        return self.submission_number


class SubmissionItem(models.Model):
    submission = models.ForeignKey(CashSubmission, on_delete=models.PROTECT, related_name="items")
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="submission_items")
    amount = MoneyField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["submission", "collection"], name="uniq_submission_collection"),
        ]

    def __str__(self):
        return f"{self.submission_id}:{self.collection_id}"


class Discrepancy(TimeStampedModel):
    class Type(models.TextChoices):
        SHORTAGE = "SHORTAGE", "Cash shortage at branch"
        EXCESS = "EXCESS", "Excess cash at branch"
        BANK_MISMATCH = "BANK_MISMATCH", "Bank deposit ≠ reconciled cash"
        SETTLEMENT_MISMATCH = "SETTLEMENT_MISMATCH", "Bank settled ≠ deposited"
        REVERSAL_ADJUSTMENT = "REVERSAL_ADJUSTMENT", "Reconciled collection reversed"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        RESOLVED = "RESOLVED", "Resolved"

    type = models.CharField(max_length=30, choices=Type.choices, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="discrepancies")
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="discrepancies"
    )
    submission = models.ForeignKey(
        CashSubmission, null=True, blank=True, on_delete=models.PROTECT, related_name="discrepancies"
    )
    deposit = models.ForeignKey(
        "deposits.BankDeposit", null=True, blank=True, on_delete=models.PROTECT, related_name="discrepancies"
    )
    collection = models.ForeignKey(
        Collection, null=True, blank=True, on_delete=models.PROTECT, related_name="discrepancies"
    )
    expected_amount = MoneyField()
    actual_amount = MoneyField()
    difference = MoneyField(help_text="expected - actual (positive = shortfall)")
    reason = models.CharField(max_length=255)
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "discrepancies"

    def __str__(self):
        return f"{self.type} {self.difference}"
