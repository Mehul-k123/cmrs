import calendar
from datetime import date
from decimal import ROUND_DOWN, Decimal

from django.db import transaction

from apps.core.audit import record_audit
from apps.core.exceptions import BusinessRuleError
from apps.core.money import PAISA, to_money
from apps.core.sequences import make_reference

from .models import Customer, Loan, RepaymentInstallment


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year, month = d.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def build_schedule(principal: Decimal, annual_rate: Decimal, tenure_months: int, first_due: date):
    """Flat-interest equal installments. Each EMI is rounded down to the paisa; the final
    installment absorbs the remainder so the schedule sums exactly to principal + interest."""
    principal = to_money(principal)
    interest = to_money(principal * Decimal(annual_rate) / Decimal(100) * Decimal(tenure_months) / Decimal(12))
    total = principal + interest
    emi = (total / tenure_months).quantize(PAISA, rounding=ROUND_DOWN)
    rows = []
    for n in range(1, tenure_months + 1):
        amount = emi if n < tenure_months else to_money(total - emi * (tenure_months - 1))
        rows.append({"number": n, "due_date": add_months(first_due, n - 1), "amount_due": amount})
    return rows


@transaction.atomic
def create_loan(*, actor, customer: Customer, principal, interest_rate, tenure_months: int,
                disbursed_on: date, first_due_date: date | None = None) -> Loan:
    if tenure_months <= 0 or to_money(principal) <= 0:
        raise BusinessRuleError("Principal and tenure must be positive.", code="invalid_loan_terms")
    loan = Loan.objects.create(
        loan_number=make_reference("LN", customer.branch.code),
        customer=customer,
        branch=customer.branch,
        principal=to_money(principal),
        interest_rate=interest_rate,
        tenure_months=tenure_months,
        disbursed_on=disbursed_on,
    )
    first_due = first_due_date or add_months(disbursed_on, 1)
    RepaymentInstallment.objects.bulk_create(
        RepaymentInstallment(loan=loan, **row)
        for row in build_schedule(loan.principal, interest_rate, tenure_months, first_due)
    )
    record_audit(actor, "loan.created", loan, after={"principal": loan.principal, "tenure": tenure_months})
    return loan
