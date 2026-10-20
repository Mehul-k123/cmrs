import json
import logging

from django.db import transaction
from django.utils import timezone

from apps.cash.models import Collection
from apps.cash.services import assert_not_over_collected, lock_loan, record_digital_collection
from apps.core.audit import record_audit
from apps.core.exceptions import BusinessRuleError
from apps.core.money import to_money
from apps.core.sequences import make_reference

from .gateway import gateway, verify_signature
from .models import PaymentIntent, WebhookEvent

logger = logging.getLogger("cmrs.payments")


@transaction.atomic
def create_intent(*, actor, loan_id: int, amount) -> tuple[PaymentIntent, dict]:
    amount = to_money(amount)
    loan = lock_loan(loan_id)
    assert_not_over_collected(loan, amount)
    order = gateway.create_order(amount, receipt=loan.loan_number)
    intent = PaymentIntent.objects.create(
        intent_number=make_reference("PI", loan.branch.code),
        gateway_ref=order["gateway_ref"], loan=loan, amount=amount, created_by=actor,
    )
    record_audit(actor, "payment_intent.created", intent, after={"amount": amount, "ref": intent.gateway_ref})
    return intent, order


def handle_webhook(body: bytes, signature: str) -> dict:
    """Verify, de-duplicate and apply a gateway event."""
    if not verify_signature(body, signature):
        raise BusinessRuleError("Invalid webhook signature.", code="invalid_signature", status_code=401)
    event = json.loads(body)
    with transaction.atomic():
        _, created = WebhookEvent.objects.get_or_create(
            event_id=event["id"], defaults={"event_type": event["type"], "payload": event}
        )
        if not created:
            return {"status": "duplicate_ignored"}
        handler = {
            "payment.captured": _on_captured,
            "payment.failed": _on_failed,
            "settlement.processed": _on_settlement,
        }.get(event["type"])
        if handler is None:
            return {"status": "ignored"}
        return handler(event["data"])


def _on_captured(data: dict) -> dict:
    intent = PaymentIntent.objects.select_for_update().get(gateway_ref=data["gateway_ref"])
    if intent.status != PaymentIntent.Status.CREATED:
        return {"status": "already_processed"}
    if to_money(data["amount"]) != intent.amount:
        # Never trust a captured amount that differs from what we asked for.
        intent.status = PaymentIntent.Status.FAILED
        intent.failure_reason = f"Amount mismatch: captured {data['amount']} vs requested {intent.amount}"
        intent.save()
        logger.warning("payment amount mismatch ref=%s", intent.gateway_ref)
        return {"status": "amount_mismatch"}
    try:
        with transaction.atomic():
            collection = record_digital_collection(loan_id=intent.loan_id, amount=intent.amount,
                                                   gateway_ref=intent.gateway_ref)
    except BusinessRuleError as exc:  # e.g. loan got paid in cash meanwhile → over-collection
        intent.status = PaymentIntent.Status.FAILED
        intent.failure_reason = f"{exc.detail} (refund required)"
        intent.save()
        return {"status": "rejected", "reason": str(exc.detail)}
    intent.status = PaymentIntent.Status.PAID
    intent.collection = collection
    intent.paid_at = timezone.now()
    intent.save()
    return {"status": "captured", "receipt_number": collection.receipt_number}


def _on_failed(data: dict) -> dict:
    intent = PaymentIntent.objects.select_for_update().get(gateway_ref=data["gateway_ref"])
    if intent.status == PaymentIntent.Status.CREATED:
        intent.status = PaymentIntent.Status.FAILED
        intent.failure_reason = data.get("reason", "Payment failed")
        intent.save()
    return {"status": "failed"}


def _on_settlement(data: dict) -> dict:
    refs = data.get("gateway_refs", [])
    intents = PaymentIntent.objects.select_for_update().filter(
        gateway_ref__in=refs, status=PaymentIntent.Status.PAID
    )
    now = timezone.now()
    count = 0
    for intent in intents:
        Collection.objects.filter(pk=intent.collection_id).update(status=Collection.Status.SETTLED)
        intent.status = PaymentIntent.Status.SETTLED
        intent.settled_at = now
        intent.save()
        count += 1
    return {"status": "settled", "count": count}


# --- Simulation helpers (mock gateway only) --------------------------------------------


def simulate_payment(intent: PaymentIntent, success: bool) -> dict:
    if success:
        body, sig = gateway.build_event("payment.captured",
                                        {"gateway_ref": intent.gateway_ref, "amount": str(intent.amount)})
    else:
        body, sig = gateway.build_event("payment.failed",
                                        {"gateway_ref": intent.gateway_ref, "reason": "Customer declined"})
    return handle_webhook(body, sig)


def simulate_settlement() -> dict:
    refs = list(PaymentIntent.objects.filter(status=PaymentIntent.Status.PAID).values_list("gateway_ref", flat=True))
    body, sig = gateway.build_event("settlement.processed", {"gateway_refs": refs})
    return handle_webhook(body, sig)
