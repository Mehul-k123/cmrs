"""Cash lifecycle business rules: collect → submit → verify (approve / reject) → reverse.

Every function runs in a transaction and locks the rows it mutates (SELECT ... FOR UPDATE) so that two
concurrent requests can never double-allocate an installment or double-approve a submission.
"""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.audit import record_audit
from apps.core.exceptions import BusinessRuleError, ConflictError
from apps.core.money import ZERO, money_sum, to_money
from apps.core.permissions import Role
from apps.core.sequences import make_reference
from apps.loans.models import Loan, RepaymentInstallment

from .models import CashSubmission, Collection, CollectionAllocation, Discrepancy, SubmissionItem

ACTIVE_STATUSES = [s for s in Collection.Status.values if s != Collection.Status.REVERSED]


# --- Loan ledger -----------------------------------------------------------------


def _allocate(collection: Collection) -> None:
    """Apply a collection to the loan's installments, oldest due first (supports partial payments)."""
    remaining = collection.amount
    installments = (
        RepaymentInstallment.objects.select_for_update()
        .filter(loan_id=collection.loan_id)
        .exclude(status=RepaymentInstallment.Status.PAID)
        .order_by("number")
    )
    for inst in installments:
        if remaining <= ZERO:
            break
        portion = min(remaining, inst.balance)
        inst.amount_paid = to_money(inst.amount_paid + portion)
        inst.refresh_status()
        inst.save(update_fields=["amount_paid", "status"])
        CollectionAllocation.objects.create(collection=collection, installment=inst, amount=portion)
        remaining = to_money(remaining - portion)
    if remaining > ZERO:  # guarded earlier; this would indicate a race or bug
        raise BusinessRuleError("Payment exceeds the outstanding amount.", code="over_collection")
    _sync_loan_status(collection.loan_id)


def _deallocate(collection: Collection) -> None:
    for alloc in collection.allocations.select_related("installment").select_for_update():
        inst = alloc.installment
        inst.amount_paid = to_money(inst.amount_paid - alloc.amount)
        inst.refresh_status()
        inst.save(update_fields=["amount_paid", "status"])
    _sync_loan_status(collection.loan_id)


def _sync_loan_status(loan_id: int) -> None:
    loan = Loan.objects.get(pk=loan_id)
    status = Loan.Status.CLOSED if loan.compute_totals()["outstanding"] <= ZERO else Loan.Status.ACTIVE
    if loan.status != status:
        loan.status = status
        loan.save(update_fields=["status", "updated_at"])


def lock_loan(loan_id: int) -> Loan:
    return Loan.objects.select_for_update().select_related("customer", "branch").get(pk=loan_id)


def assert_not_over_collected(loan: Loan, amount) -> None:
    outstanding = loan.compute_totals()["outstanding"]
    if outstanding <= ZERO:
        raise BusinessRuleError("This loan has no outstanding amount.", code="loan_fully_paid",
                                details={"outstanding": str(outstanding)})
    if amount > outstanding:
        raise BusinessRuleError(
            f"Amount ₹{amount} exceeds the outstanding ₹{outstanding}. Over-collection is not allowed.",
            code="over_collection",
            details={"outstanding": str(outstanding), "amount": str(amount)},
        )


# --- Collect ---------------------------------------------------------------------


def record_cash_collection(*, agent, loan_id: int, amount, idempotency_key: str, collected_at=None,
                           notes: str = "", confirm_duplicate: bool = False) -> tuple[Collection, bool]:
    """Record a cash repayment. Returns (collection, created). A replay with the same idempotency key
    returns the original collection instead of creating a second one."""
    amount = to_money(amount)
    if amount <= ZERO:
        raise BusinessRuleError("Amount must be greater than zero.", code="invalid_amount")
    if not idempotency_key:
        raise BusinessRuleError("Idempotency-Key header is required.", code="idempotency_key_required")
    if collected_at and collected_at > timezone.now() + timedelta(minutes=5):
        raise BusinessRuleError("Collection time cannot be in the future.", code="invalid_date")

    existing = Collection.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if existing.agent_id == agent.id and existing.loan_id == loan_id and existing.amount == amount:
            return existing, False
        raise ConflictError("This idempotency key was already used for a different payment.",
                            code="idempotency_key_reused")

    with transaction.atomic():
        loan = lock_loan(loan_id)  # serialises concurrent collections on the same loan
        if loan.customer.assigned_agent_id != agent.id:
            raise BusinessRuleError("This customer is not assigned to you.", code="not_assigned",
                                    status_code=403)
        assert_not_over_collected(loan, amount)

        window = timezone.now() - timedelta(minutes=settings.DUPLICATE_COLLECTION_WINDOW_MINUTES)
        recent = Collection.objects.filter(
            loan=loan, amount=amount, created_at__gte=window, status__in=ACTIVE_STATUSES
        ).first()
        if recent and not confirm_duplicate:
            raise ConflictError(
                f"A collection of ₹{amount} was already recorded for this loan at "
                f"{timezone.localtime(recent.created_at):%H:%M} (receipt {recent.receipt_number}). "
                "Confirm if this is a genuine second payment.",
                code="possible_duplicate",
                details={"receipt_number": recent.receipt_number},
            )

        try:
            with transaction.atomic():
                collection = Collection.objects.create(
                    receipt_number=make_reference("RCP", loan.branch.code),
                    loan=loan,
                    customer=loan.customer,
                    branch=loan.branch,
                    agent=agent,
                    amount=amount,
                    mode=Collection.Mode.CASH,
                    collected_at=collected_at or timezone.now(),
                    idempotency_key=idempotency_key,
                    notes=notes,
                )
        except IntegrityError:
            # Lost a race with a concurrent request carrying the same idempotency key.
            existing = Collection.objects.get(idempotency_key=idempotency_key)
            return existing, False
        _allocate(collection)
        record_audit(agent, "collection.recorded", collection,
                     after={"amount": amount, "loan": loan.loan_number, "receipt": collection.receipt_number,
                            "confirmed_duplicate": bool(recent)})
    return collection, True


def record_digital_collection(*, loan_id: int, amount, gateway_ref: str) -> Collection:
    """Called from the payment gateway webhook. UPI money bypasses agent and branch cash handling."""
    amount = to_money(amount)
    with transaction.atomic():
        loan = lock_loan(loan_id)
        assert_not_over_collected(loan, amount)
        collection = Collection.objects.create(
            receipt_number=make_reference("UPI", loan.branch.code),
            loan=loan,
            customer=loan.customer,
            branch=loan.branch,
            agent=None,
            amount=amount,
            mode=Collection.Mode.UPI,
            collected_at=timezone.now(),
            idempotency_key=f"gw:{gateway_ref}",
            payment_reference=gateway_ref,
            is_locked=True,  # gateway-confirmed money is immutable from day one
        )
        _allocate(collection)
        record_audit(None, "collection.digital_received", collection,
                     after={"amount": amount, "gateway_ref": gateway_ref})
    return collection


# --- Submit to branch ----------------------------------------------------------------


@transaction.atomic
def create_submission(*, agent, collection_ids: list[int], declared_amount, note: str = "") -> CashSubmission:
    if not collection_ids:
        raise BusinessRuleError("Select at least one collection to submit.", code="empty_submission")
    collections = list(
        Collection.objects.select_for_update().filter(pk__in=set(collection_ids)).order_by("pk")
    )
    if len(collections) != len(set(collection_ids)):
        raise BusinessRuleError("Some collections were not found.", code="collection_not_found")
    invalid = [c.receipt_number for c in collections
               if c.agent_id != agent.id or c.mode != Collection.Mode.CASH
               or c.status != Collection.Status.COLLECTED]
    if invalid:
        raise BusinessRuleError(
            "Only your own cash collections that are still with you can be submitted.",
            code="invalid_collections", details={"receipts": invalid},
        )
    expected = money_sum(c.amount for c in collections)
    declared = to_money(declared_amount if declared_amount is not None else expected)
    if declared < ZERO:
        raise BusinessRuleError("Declared amount cannot be negative.", code="invalid_amount")

    submission = CashSubmission.objects.create(
        submission_number=make_reference("SUB", agent.branch.code),
        agent=agent,
        branch=agent.branch,
        expected_amount=expected,
        declared_amount=declared,
        agent_note=note,
    )
    SubmissionItem.objects.bulk_create(
        SubmissionItem(submission=submission, collection=c, amount=c.amount) for c in collections
    )
    Collection.objects.filter(pk__in=[c.pk for c in collections]).update(status=Collection.Status.SUBMITTED)
    record_audit(agent, "submission.created", submission,
                 after={"expected": expected, "declared": declared, "collections": len(collections)})
    return submission


def _lock_submission_for_review(submission_id: int, reviewer) -> CashSubmission:
    submission = CashSubmission.objects.select_for_update().select_related("branch").get(pk=submission_id)
    if reviewer.role == Role.BRANCH_MANAGER and submission.branch_id != reviewer.branch_id:
        raise BusinessRuleError("You can only review submissions for your branch.", code="forbidden_branch",
                                status_code=403)
    if submission.status != CashSubmission.Status.SUBMITTED:
        raise ConflictError(f"Submission is already {submission.status.lower()}.", code="already_reviewed")
    if submission.agent_id == reviewer.id:
        raise BusinessRuleError("You cannot review your own submission.", code="self_review", status_code=403)
    return submission


@transaction.atomic
def approve_submission(*, reviewer, submission_id: int, received_amount, note: str = "") -> CashSubmission:
    """Branch verifies the physical cash. Any difference is recorded as a discrepancy and the
    submission is reconciled at the amount actually received."""
    submission = _lock_submission_for_review(submission_id, reviewer)
    received = to_money(received_amount)
    if received < ZERO:
        raise BusinessRuleError("Received amount cannot be negative.", code="invalid_amount")
    difference = to_money(submission.expected_amount - received)
    if difference != ZERO and not note.strip():
        raise BusinessRuleError(
            "Received amount differs from expected; a reason is required.",
            code="discrepancy_reason_required",
            details={"expected": str(submission.expected_amount), "received": str(received),
                     "difference": str(difference)},
        )

    before = {"status": submission.status}
    submission.received_amount = received
    submission.difference = difference
    submission.status = CashSubmission.Status.APPROVED
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.review_note = note
    submission.save()

    Collection.objects.filter(submission_items__submission=submission).update(
        status=Collection.Status.BRANCH_RECEIVED, is_locked=True
    )
    if difference != ZERO:
        Discrepancy.objects.create(
            type=Discrepancy.Type.SHORTAGE if difference > ZERO else Discrepancy.Type.EXCESS,
            branch=submission.branch,
            agent=submission.agent,
            submission=submission,
            expected_amount=submission.expected_amount,
            actual_amount=received,
            difference=difference,
            reason=note,
            raised_by=reviewer,
        )
    record_audit(reviewer, "submission.approved", submission, before=before,
                 after={"status": submission.status, "received": received, "difference": difference})
    return submission


@transaction.atomic
def reject_submission(*, reviewer, submission_id: int, reason: str) -> CashSubmission:
    """Cash goes back to the agent's custody; the collections can be resubmitted."""
    if not reason.strip():
        raise BusinessRuleError("A rejection reason is required.", code="reason_required")
    submission = _lock_submission_for_review(submission_id, reviewer)
    submission.status = CashSubmission.Status.REJECTED
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.review_note = reason
    submission.save()
    Collection.objects.filter(submission_items__submission=submission).update(
        status=Collection.Status.COLLECTED
    )
    record_audit(reviewer, "submission.rejected", submission,
                 before={"status": CashSubmission.Status.SUBMITTED}, after={"status": submission.status,
                                                                            "reason": reason})
    return submission


# --- Corrections --------------------------------------------------------------------


@transaction.atomic
def reverse_collection(*, actor, collection_id: int, reason: str) -> Collection:
    """The only way to undo a collection. Restores the loan balance. Reversing an already-reconciled
    collection is restricted to admins and opens an adjustment discrepancy for finance follow-up."""
    if not reason.strip():
        raise BusinessRuleError("A reversal reason is required.", code="reason_required")
    collection = Collection.objects.select_for_update().get(pk=collection_id)
    lock_loan(collection.loan_id)
    if collection.status == Collection.Status.REVERSED:
        raise ConflictError("Collection is already reversed.", code="already_reversed")
    if collection.status == Collection.Status.SUBMITTED:
        raise BusinessRuleError("Collection is pending branch verification; reject the submission first.",
                                code="pending_submission")
    if collection.is_locked and actor.role != Role.ADMIN:
        raise BusinessRuleError("Reconciled collections can only be reversed by an admin.",
                                code="locked", status_code=403)

    before = {"status": collection.status}
    was_locked = collection.is_locked
    _deallocate(collection)
    collection.status = Collection.Status.REVERSED
    collection.reversed_at = timezone.now()
    collection.reversed_by = actor
    collection.reversal_reason = reason
    collection.save(update_fields=["status", "reversed_at", "reversed_by", "reversal_reason", "updated_at"])
    if was_locked:
        Discrepancy.objects.create(
            type=Discrepancy.Type.REVERSAL_ADJUSTMENT,
            branch=collection.branch,
            agent=collection.agent,
            collection=collection,
            expected_amount=collection.amount,
            actual_amount=ZERO,
            difference=collection.amount,
            reason=reason,
            raised_by=actor,
        )
    record_audit(actor, "collection.reversed", collection, before=before,
                 after={"status": collection.status, "reason": reason})
    return collection


@transaction.atomic
def resolve_discrepancy(*, actor, discrepancy_id: int, note: str) -> Discrepancy:
    if not note.strip():
        raise BusinessRuleError("A resolution note is required.", code="reason_required")
    d = Discrepancy.objects.select_for_update().get(pk=discrepancy_id)
    if actor.role == Role.BRANCH_MANAGER and d.branch_id != actor.branch_id:
        raise BusinessRuleError("Not your branch.", code="forbidden_branch", status_code=403)
    if d.status == Discrepancy.Status.RESOLVED:
        raise ConflictError("Discrepancy is already resolved.", code="already_resolved")
    d.status = Discrepancy.Status.RESOLVED
    d.resolved_by = actor
    d.resolved_at = timezone.now()
    d.resolution_note = note
    d.save()
    record_audit(actor, "discrepancy.resolved", d, before={"status": "OPEN"}, after={"note": note})
    return d
