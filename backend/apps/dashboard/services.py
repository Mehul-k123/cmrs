"""Dashboard aggregates. All sums are done in Postgres on NUMERIC columns and returned as strings."""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Abs, Coalesce, TruncDate
from django.utils import timezone

from apps.cash.models import CashSubmission, Collection, Discrepancy
from apps.core.money import to_money
from apps.core.permissions import Role
from apps.deposits.models import BankDeposit
from apps.loans.models import Loan, RepaymentInstallment

ZERO_DEC = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
CS = Collection.Status


def _sum(qs, field="amount") -> str:
    return str(to_money(qs.aggregate(t=Coalesce(Sum(field), ZERO_DEC))["t"]))


@dataclass
class DashboardFilters:
    date_from: date
    date_to: date
    branch: int | None = None
    agent: int | None = None
    status: str | None = None

    @classmethod
    def from_request(cls, request):
        p = request.query_params
        today = timezone.localdate()
        f = cls(
            date_from=date.fromisoformat(p["date_from"]) if p.get("date_from") else today - timedelta(days=29),
            date_to=date.fromisoformat(p["date_to"]) if p.get("date_to") else today,
            branch=int(p["branch"]) if p.get("branch") else None,
            agent=int(p["agent"]) if p.get("agent") else None,
            status=p.get("status") or None,
        )
        user = request.user  # row-level scoping overrides whatever the client asked for
        if user.role == Role.BRANCH_MANAGER:
            f.branch = user.branch_id
        elif user.role == Role.AGENT:
            f.branch, f.agent = user.branch_id, user.id
        return f


def build_summary(f: DashboardFilters) -> dict:
    in_range = {"collected_at__date__gte": f.date_from, "collected_at__date__lte": f.date_to}

    collections = Collection.objects.filter(**in_range)
    installments = RepaymentInstallment.objects.filter(due_date__gte=f.date_from, due_date__lte=f.date_to)
    loans = Loan.objects.filter(status=Loan.Status.ACTIVE)
    submissions = CashSubmission.objects.filter(reviewed_at__date__gte=f.date_from, reviewed_at__date__lte=f.date_to)
    deposits = BankDeposit.objects.filter(deposit_date__gte=f.date_from, deposit_date__lte=f.date_to)
    settled_deposits = BankDeposit.objects.filter(status=BankDeposit.Status.SETTLED,
                                                  settled_on__gte=f.date_from, settled_on__lte=f.date_to)
    discrepancies = Discrepancy.objects.filter(created_at__date__gte=f.date_from, created_at__date__lte=f.date_to)

    if f.branch:
        collections = collections.filter(branch=f.branch)
        installments = installments.filter(loan__branch=f.branch)
        loans = loans.filter(branch=f.branch)
        submissions = submissions.filter(branch=f.branch)
        deposits = deposits.filter(branch=f.branch)
        settled_deposits = settled_deposits.filter(branch=f.branch)
        discrepancies = discrepancies.filter(branch=f.branch)
    if f.agent:
        collections = collections.filter(agent=f.agent)
        installments = installments.filter(loan__customer__assigned_agent=f.agent)
        loans = loans.filter(customer__assigned_agent=f.agent)
        submissions = submissions.filter(agent=f.agent)
        discrepancies = discrepancies.filter(agent=f.agent)
        # deposits are branch-level and cannot be attributed to a single agent
        deposits = deposits.filter(submissions__agent=f.agent).distinct()
        settled_deposits = settled_deposits.filter(submissions__agent=f.agent).distinct()
    if f.status:
        collections = collections.filter(status=f.status)

    active = collections.exclude(status=CS.REVERSED)
    cash = active.filter(mode=Collection.Mode.CASH)
    reconciled = submissions.filter(status__in=[CashSubmission.Status.APPROVED, CashSubmission.Status.DEPOSITED,
                                                CashSubmission.Status.SETTLED])
    open_disc = discrepancies.filter(status=Discrepancy.Status.OPEN)
    outstanding_qs = RepaymentInstallment.objects.filter(loan__in=loans)
    outstanding = to_money(outstanding_qs.aggregate(
        t=Coalesce(Sum(F("amount_due") - F("amount_paid")), ZERO_DEC))["t"])
    overdue = to_money(outstanding_qs.filter(due_date__lt=timezone.localdate()).aggregate(
        t=Coalesce(Sum(F("amount_due") - F("amount_paid")), ZERO_DEC))["t"])

    settled_digital = active.filter(mode=Collection.Mode.UPI, status=CS.SETTLED)
    settled_cash = to_money(settled_deposits.aggregate(t=Coalesce(Sum("settled_amount"), ZERO_DEC))["t"])

    kpis = {
        "expected_collections": _sum(installments, "amount_due"),
        "total_collected": _sum(active),
        "collected_cash": _sum(cash),
        "collected_digital": _sum(active.filter(mode=Collection.Mode.UPI)),
        "cash_with_agents": _sum(cash.filter(status__in=[CS.COLLECTED, CS.SUBMITTED])),
        "cash_pending_verification": _sum(cash.filter(status=CS.SUBMITTED)),
        "received_at_branches": _sum(reconciled, "received_amount"),
        "awaiting_bank_deposit": _sum(
            CashSubmission.objects.filter(status=CashSubmission.Status.APPROVED,
                                          **({"branch": f.branch} if f.branch else {}),
                                          **({"agent": f.agent} if f.agent else {})),
            "received_amount"),
        "bank_deposited": _sum(deposits.exclude(status=BankDeposit.Status.FAILED)),
        "pending_settlement": _sum(deposits.filter(status=BankDeposit.Status.DEPOSITED)),
        "settled_amount": str(to_money(settled_cash + to_money(
            settled_digital.aggregate(t=Coalesce(Sum("amount"), ZERO_DEC))["t"]))),
        "settled_cash": str(settled_cash),
        "settled_digital": _sum(settled_digital),
        "outstanding_amount": str(outstanding),
        "overdue_amount": str(overdue),
        "open_discrepancies": open_disc.count(),
        "open_discrepancy_amount": _sum(open_disc.annotate(abs_diff=Abs("difference")), "abs_diff"),
        "failed_deposits": deposits.filter(status=BankDeposit.Status.FAILED).count(),
        "delayed_settlements": BankDeposit.objects.with_delay_flag()
        .filter(is_delayed=True, **({"branch": f.branch} if f.branch else {})).count(),
    }
    kpis["collection_efficiency_pct"] = (
        str((to_money(kpis["total_collected"]) / to_money(kpis["expected_collections"]) * 100).quantize(
            to_money("0.1")))
        if to_money(kpis["expected_collections"]) > 0 else None
    )

    lifecycle = {s: "0.00" for s in CS.values}
    for row in collections.values("status").annotate(t=Sum("amount")):
        lifecycle[row["status"]] = str(to_money(row["t"]))

    daily = {
        r["day"]: r
        for r in active.annotate(day=TruncDate("collected_at")).values("day").annotate(
            cash=Coalesce(Sum("amount", filter=Q(mode=Collection.Mode.CASH)), ZERO_DEC),
            digital=Coalesce(Sum("amount", filter=Q(mode=Collection.Mode.UPI)), ZERO_DEC),
        )
    }
    trend = []  # one row per calendar day so the time axis is continuous
    day = f.date_from
    while day <= f.date_to:
        row = daily.get(day, {})
        trend.append({"date": day.isoformat(), "cash": str(to_money(row.get("cash"))),
                      "digital": str(to_money(row.get("digital")))})
        day += timedelta(days=1)

    by_branch = [
        {"branch_id": r["branch"], "branch": r["branch__name"], "collected": str(to_money(r["collected"])),
         "cash_with_agents": str(to_money(r["held"])), "count": r["n"]}
        for r in active.values("branch", "branch__name").annotate(
            collected=Sum("amount"), n=Count("id"),
            held=Coalesce(Sum("amount", filter=Q(mode=Collection.Mode.CASH, status__in=[CS.COLLECTED, CS.SUBMITTED])),
                          ZERO_DEC),
        ).order_by("branch__name")
    ]

    shortage_by_agent = {
        r["agent"]: to_money(r["t"])
        for r in discrepancies.filter(type=Discrepancy.Type.SHORTAGE).values("agent").annotate(t=Sum("difference"))
    }
    by_agent = [
        {"agent_id": r["agent"], "agent": f'{r["agent__first_name"]} {r["agent__last_name"]}'.strip()
         or r["agent__username"], "collected": str(to_money(r["collected"])),
         "cash_in_hand": str(to_money(r["in_hand"])), "pending_verification": str(to_money(r["pending"])),
         "shortages": str(shortage_by_agent.get(r["agent"], to_money(0))), "count": r["n"]}
        for r in cash.values("agent", "agent__first_name", "agent__last_name", "agent__username").annotate(
            collected=Sum("amount"), n=Count("id"),
            in_hand=Coalesce(Sum("amount", filter=Q(status=CS.COLLECTED)), ZERO_DEC),
            pending=Coalesce(Sum("amount", filter=Q(status=CS.SUBMITTED)), ZERO_DEC),
        ).order_by("-collected")
    ]

    disc_by_type = [
        {"type": r["type"], "count": r["n"], "amount": str(to_money(r["t"]))}
        for r in open_disc.values("type").annotate(n=Count("id"), t=Sum(Abs("difference"))).order_by("type")
    ]

    return {
        "filters": {"date_from": f.date_from.isoformat(), "date_to": f.date_to.isoformat(), "branch": f.branch,
                    "agent": f.agent, "status": f.status},
        "kpis": kpis,
        "lifecycle": lifecycle,
        "trend": trend,
        "by_branch": by_branch,
        "by_agent": by_agent,
        "discrepancies_by_type": disc_by_type,
    }
