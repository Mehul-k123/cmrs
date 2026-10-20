"""Bank deposit and settlement rules: Branch Received → Bank Deposited → Settled (or Failed)."""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.cash.models import CashSubmission, Collection, Discrepancy
from apps.core.audit import record_audit
from apps.core.exceptions import BusinessRuleError, ConflictError
from apps.core.money import ZERO, money_sum, to_money
from apps.core.permissions import Role
from apps.core.sequences import make_reference

from .models import BankDeposit


def normalise_reference(ref: str) -> str:
    return "".join(ref.split()).upper()


@transaction.atomic
def create_deposit(*, actor, branch, submission_ids: list[int], bank_name: str, account_number: str,
                   reference_number: str, deposit_date, amount, mismatch_reason: str = "") -> BankDeposit:
    if actor.role == Role.BRANCH_MANAGER and branch.id != actor.branch_id:
        raise BusinessRuleError("You can only deposit for your own branch.", code="forbidden_branch",
                                status_code=403)
    if not submission_ids:
        raise BusinessRuleError("Select at least one approved submission.", code="empty_deposit")
    if deposit_date > timezone.localdate():
        raise BusinessRuleError("Deposit date cannot be in the future.", code="invalid_date")

    bank_name = bank_name.strip()
    reference_number = normalise_reference(reference_number)
    if BankDeposit.objects.filter(bank_name__iexact=bank_name, reference_number=reference_number).exists():
        raise ConflictError(f"Bank reference {reference_number} is already recorded for {bank_name}.",
                            code="duplicate_bank_reference")

    submissions = list(
        CashSubmission.objects.select_for_update().filter(pk__in=set(submission_ids)).order_by("pk")
    )
    if len(submissions) != len(set(submission_ids)):
        raise BusinessRuleError("Some submissions were not found.", code="submission_not_found")
    invalid = [s.submission_number for s in submissions
               if s.branch_id != branch.id or s.status != CashSubmission.Status.APPROVED]
    if invalid:
        raise BusinessRuleError("Only approved, not-yet-deposited submissions of this branch can be deposited.",
                                code="invalid_submissions", details={"submissions": invalid})

    reconciled = money_sum(s.received_amount for s in submissions)
    amount = to_money(amount)
    difference = to_money(reconciled - amount)
    if difference != ZERO and not mismatch_reason.strip():
        raise BusinessRuleError(
            "Deposit amount does not match the reconciled cash; a reason is required.",
            code="deposit_mismatch_reason_required",
            details={"reconciled": str(reconciled), "amount": str(amount), "difference": str(difference)},
        )

    try:
        with transaction.atomic():
            deposit = BankDeposit.objects.create(
                deposit_number=make_reference("DEP", branch.code),
                branch=branch,
                bank_name=bank_name,
                account_number=account_number.strip(),
                reference_number=reference_number,
                deposit_date=deposit_date,
                reconciled_amount=reconciled,
                amount=amount,
                mismatch_reason=mismatch_reason,
                created_by=actor,
            )
    except IntegrityError as exc:  # concurrent insert with the same reference
        raise ConflictError(f"Bank reference {reference_number} is already recorded.",
                            code="duplicate_bank_reference") from exc
    deposit.submissions.set(submissions)
    CashSubmission.objects.filter(pk__in=[s.pk for s in submissions]).update(
        status=CashSubmission.Status.DEPOSITED
    )
    Collection.objects.filter(submission_items__submission__in=submissions,
                              status=Collection.Status.BRANCH_RECEIVED).update(status=Collection.Status.DEPOSITED)
    if difference != ZERO:
        Discrepancy.objects.create(
            type=Discrepancy.Type.BANK_MISMATCH, branch=branch, deposit=deposit,
            expected_amount=reconciled, actual_amount=amount, difference=difference,
            reason=mismatch_reason, raised_by=actor,
        )
    record_audit(actor, "deposit.created", deposit,
                 after={"amount": amount, "reconciled": reconciled, "reference": reference_number,
                        "submissions": [s.submission_number for s in submissions]})
    return deposit


def _lock_pending(deposit_id: int) -> BankDeposit:
    deposit = BankDeposit.objects.select_for_update().get(pk=deposit_id)
    if deposit.status != BankDeposit.Status.DEPOSITED:
        raise ConflictError(f"Deposit is already {deposit.status.lower()}.", code="already_finalised")
    return deposit


@transaction.atomic
def settle_deposit(*, actor, deposit_id: int, settled_amount, settled_on, settlement_reference: str,
                   note: str = "") -> BankDeposit:
    deposit = _lock_pending(deposit_id)
    settled = to_money(settled_amount)
    difference = to_money(deposit.amount - settled)
    if difference != ZERO and not note.strip():
        raise BusinessRuleError(
            "Settled amount differs from deposited amount; a reason is required.",
            code="settlement_mismatch_reason_required",
            details={"deposited": str(deposit.amount), "settled": str(settled), "difference": str(difference)},
        )
    if settled_on < deposit.deposit_date:
        raise BusinessRuleError("Settlement date cannot be before the deposit date.", code="invalid_date")

    deposit.status = BankDeposit.Status.SETTLED
    deposit.settled_amount = settled
    deposit.settled_on = settled_on
    deposit.settlement_reference = settlement_reference.strip()
    deposit.settled_by = actor
    deposit.save()
    subs = deposit.submissions.all()
    subs.update(status=CashSubmission.Status.SETTLED)
    Collection.objects.filter(submission_items__submission__in=subs, status=Collection.Status.DEPOSITED).update(
        status=Collection.Status.SETTLED
    )
    if difference != ZERO:
        Discrepancy.objects.create(
            type=Discrepancy.Type.SETTLEMENT_MISMATCH, branch=deposit.branch, deposit=deposit,
            expected_amount=deposit.amount, actual_amount=settled, difference=difference,
            reason=note, raised_by=actor,
        )
    record_audit(actor, "deposit.settled", deposit, before={"status": BankDeposit.Status.DEPOSITED},
                 after={"settled_amount": settled, "difference": difference})
    return deposit


@transaction.atomic
def fail_deposit(*, actor, deposit_id: int, reason: str) -> BankDeposit:
    """Bank rejected/returned the deposit: the cash is back at the branch and can be redeposited."""
    if not reason.strip():
        raise BusinessRuleError("A failure reason is required.", code="reason_required")
    deposit = _lock_pending(deposit_id)
    deposit.status = BankDeposit.Status.FAILED
    deposit.failure_reason = reason
    deposit.save()
    subs = deposit.submissions.all()
    subs.update(status=CashSubmission.Status.APPROVED)
    Collection.objects.filter(submission_items__submission__in=subs, status=Collection.Status.DEPOSITED).update(
        status=Collection.Status.BRANCH_RECEIVED
    )
    record_audit(actor, "deposit.failed", deposit, before={"status": BankDeposit.Status.DEPOSITED},
                 after={"status": deposit.status, "reason": reason})
    return deposit


def flag_delayed_deposits() -> list[BankDeposit]:
    """Mark deposits pending beyond the settlement SLA (run daily via cron)."""
    delayed = list(BankDeposit.objects.with_delay_flag().filter(is_delayed=True, delay_flagged_at__isnull=True))
    now = timezone.now()
    for d in delayed:
        BankDeposit.objects.filter(pk=d.pk).update(delay_flagged_at=now)
        record_audit(None, "deposit.settlement_delayed", d, after={"deposit_date": d.deposit_date})
    return delayed
