from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.fields import MoneyField
from apps.core.models import TimeStampedModel


class PaymentIntent(TimeStampedModel):
    """A digital (UPI) repayment request sent through the payment gateway."""

    class Status(models.TextChoices):
        CREATED = "CREATED", "Awaiting payment"
        PAID = "PAID", "Paid (captured)"
        FAILED = "FAILED", "Failed"
        SETTLED = "SETTLED", "Settled by gateway"

    intent_number = models.CharField(max_length=40, unique=True)
    gateway_ref = models.CharField(max_length=64, unique=True)
    loan = models.ForeignKey("loans.Loan", on_delete=models.PROTECT, related_name="payment_intents")
    amount = MoneyField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CREATED, db_index=True)
    collection = models.OneToOneField(
        "cash.Collection", null=True, blank=True, on_delete=models.PROTECT, related_name="payment_intent"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    failure_reason = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="intent_amount_positive")]

    def __str__(self):
        return self.intent_number


class WebhookEvent(models.Model):
    """Every webhook delivery is stored; event_id uniqueness makes processing idempotent."""

    event_id = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=40)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type} {self.event_id}"
