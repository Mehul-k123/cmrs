from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Case, Q, Value, When
from django.utils import timezone

from apps.core.fields import MoneyField
from apps.core.models import TimeStampedModel


class BankDepositQuerySet(models.QuerySet):
    def with_delay_flag(self):
        cutoff = timezone.localdate() - timedelta(days=settings.SETTLEMENT_SLA_DAYS)
        return self.annotate(
            is_delayed=Case(
                When(status=BankDeposit.Status.DEPOSITED, deposit_date__lt=cutoff, then=Value(True)),
                default=Value(False),
                output_field=models.BooleanField(),
            )
        )


class BankDeposit(TimeStampedModel):
    """Cash reconciled at a branch and deposited into the company bank account."""

    class Status(models.TextChoices):
        DEPOSITED = "DEPOSITED", "Deposited – awaiting settlement"
        SETTLED = "SETTLED", "Settled"
        FAILED = "FAILED", "Failed / returned"

    deposit_number = models.CharField(max_length=40, unique=True)
    branch = models.ForeignKey("core.Branch", on_delete=models.PROTECT, related_name="deposits")
    submissions = models.ManyToManyField("cash.CashSubmission", related_name="deposits")
    bank_name = models.CharField(max_length=80)
    account_number = models.CharField(max_length=30)
    reference_number = models.CharField(max_length=60, help_text="Bank slip / transaction reference")
    deposit_date = models.DateField(db_index=True)
    reconciled_amount = MoneyField(help_text="Sum of branch-received cash for the submissions")
    amount = MoneyField(help_text="Amount actually deposited")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DEPOSITED, db_index=True)
    mismatch_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    settled_amount = MoneyField(null=True, blank=True, help_text="Amount credited per bank statement")
    settled_on = models.DateField(null=True, blank=True)
    settlement_reference = models.CharField(max_length=60, blank=True)
    settled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    failure_reason = models.CharField(max_length=255, blank=True)
    delay_flagged_at = models.DateTimeField(null=True, blank=True)

    objects = BankDepositQuerySet.as_manager()

    class Meta:
        ordering = ["-deposit_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["bank_name", "reference_number"], name="uniq_bank_reference"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="deposit_amount_positive"),
            models.CheckConstraint(
                condition=Q(settled_amount__isnull=True) | Q(settled_amount__gte=0),
                name="deposit_settled_non_negative",
            ),
        ]

    def __str__(self):
        return self.deposit_number
