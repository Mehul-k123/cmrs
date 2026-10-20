from decimal import Decimal

import pytest

from apps.cash.models import Collection
from apps.loans.models import RepaymentInstallment

from .conftest import client_for, collect


def test_partial_payment_allocates_oldest_first(loan, agent):
    resp = collect(agent, loan, "1500.50")
    assert resp.status_code == 201
    assert resp.data["receipt_number"].startswith("RCP-MUM-")
    inst = list(RepaymentInstallment.objects.filter(loan=loan).order_by("number")[:3])
    assert [i.status for i in inst] == ["PAID", "PARTIAL", "PENDING"]
    assert inst[1].amount_paid == Decimal("500.50")
    assert loan.compute_totals()["outstanding"] == Decimal("10499.50")


def test_over_collection_rejected(loan, agent):
    resp = collect(agent, loan, "12000.01")
    assert resp.status_code == 400
    assert resp.data["code"] == "over_collection"
    assert resp.data["details"]["outstanding"] == "12000.00"


def test_full_repayment_closes_loan(loan, agent):
    assert collect(agent, loan, "12000").status_code == 201
    loan.refresh_from_db()
    assert loan.status == "CLOSED"
    assert collect(agent, loan, "1").data["code"] == "loan_fully_paid"


def test_idempotent_replay_returns_same_receipt(loan, agent):
    first = collect(agent, loan, "1000", key="k-1")
    replay = collect(agent, loan, "1000", key="k-1")
    assert first.status_code == 201 and replay.status_code == 200
    assert first.data["receipt_number"] == replay.data["receipt_number"]
    assert Collection.objects.count() == 1


def test_idempotency_key_reuse_with_different_payload_conflicts(loan, agent):
    collect(agent, loan, "1000", key="k-2")
    assert collect(agent, loan, "999", key="k-2").status_code == 409


def test_possible_duplicate_needs_confirmation(loan, agent):
    collect(agent, loan, "1000")
    dup = collect(agent, loan, "1000")
    assert dup.status_code == 409 and dup.data["code"] == "possible_duplicate"
    assert collect(agent, loan, "1000", confirm_duplicate=True).status_code == 201


def test_missing_idempotency_key(loan, agent):
    resp = client_for(agent).post("/api/collections/", {"loan": loan.pk, "amount": "10"}, format="json")
    assert resp.data["code"] == "idempotency_key_required"


def test_agent_cannot_collect_for_unassigned_customer(loan, other_agent):
    assert collect(other_agent, loan, "100").status_code == 403


def test_manager_cannot_record_collection(loan, manager):
    assert collect(manager, loan, "100").status_code == 403


@pytest.mark.parametrize("amount", ["0", "-5", "abc", "10.001"])
def test_invalid_amounts(loan, agent, amount):
    assert collect(agent, loan, amount).status_code == 400


def test_no_update_or_delete_endpoints(loan, agent, admin_user):
    cid = collect(agent, loan, "100").data["id"]
    c = client_for(admin_user)
    assert c.patch(f"/api/collections/{cid}/", {"amount": "1"}, format="json").status_code == 405
    assert c.delete(f"/api/collections/{cid}/").status_code == 405


def test_daily_collections(loan, agent):
    collect(agent, loan, "100")
    collect(agent, loan, "200")
    data = client_for(agent).get("/api/collections/daily/").data
    assert data["count"] == 2 and data["total"] == "300.00" and data["cash_in_hand"] == "300.00"


def test_reverse_unsubmitted_collection_restores_balance(loan, agent, manager):
    cid = collect(agent, loan, "1500").data["id"]
    resp = client_for(manager).post(f"/api/collections/{cid}/reverse/", {"reason": "wrong loan"}, format="json")
    assert resp.status_code == 200 and resp.data["status"] == "REVERSED"
    assert loan.compute_totals()["outstanding"] == Decimal("12000.00")
