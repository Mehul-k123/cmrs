from datetime import date
from decimal import Decimal

from apps.core.money import money_sum, to_money
from apps.loans.services import add_months, build_schedule

from .conftest import client_for


def test_schedule_sums_exactly_with_rounding_absorbed_by_last_installment():
    rows = build_schedule(Decimal("10000"), Decimal("13.5"), 7, date(2026, 1, 31))
    total = to_money(Decimal("10000") + Decimal("10000") * Decimal("13.5") / 100 * 7 / 12)
    assert money_sum(r["amount_due"] for r in rows) == total
    assert all(r["amount_due"].as_tuple().exponent == -2 for r in rows)
    assert rows[0]["amount_due"] <= rows[-1]["amount_due"]


def test_add_months_clamps_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_floats_are_rejected_for_money():
    import pytest

    with pytest.raises(TypeError):
        to_money(0.1)


def test_loan_detail_shows_outstanding(loan, agent):
    resp = client_for(agent).get(f"/api/loans/{loan.pk}/")
    assert resp.status_code == 200
    assert resp.data["outstanding"] == "12000.00"
    assert resp.data["total_paid"] == "0.00"


def test_agent_only_sees_assigned_customers(customer, other_agent):
    assert client_for(other_agent).get("/api/customers/").data["count"] == 0
    assert client_for(other_agent).get(f"/api/customers/{customer.pk}/").status_code == 404


def test_manager_cannot_create_customer_in_other_branch(manager, other_branch):
    resp = client_for(manager).post("/api/customers/", {"name": "X", "phone": "1", "branch": other_branch.pk},
                                    format="json")
    assert resp.status_code == 403


def test_agent_cannot_create_loan(agent, customer):
    resp = client_for(agent).post("/api/loans/", {"customer": customer.pk, "principal": "1000", "interest_rate": "10",
                                                  "tenure_months": 3, "disbursed_on": "2026-01-01"}, format="json")
    assert resp.status_code == 403
