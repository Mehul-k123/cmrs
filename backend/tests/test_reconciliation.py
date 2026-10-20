from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.cash.models import Collection, Discrepancy
from apps.deposits.models import BankDeposit
from apps.deposits.services import flag_delayed_deposits

from .conftest import client_for, collect


@pytest.fixture
def two_collections(loan, agent):
    return [collect(agent, loan, "5000").data["id"],
            collect(agent, loan, "4000").data["id"]]


def submit(agent, ids, declared=None):
    body = {"collection_ids": ids}
    if declared:
        body["declared_amount"] = declared
    return client_for(agent).post("/api/submissions/", body, format="json")


def approve(manager, sid, received, note=""):
    return client_for(manager).post(f"/api/submissions/{sid}/approve/",
                                    {"received_amount": received, "note": note}, format="json")


def test_submission_and_exact_approval(agent, manager, two_collections):
    sub = submit(agent, two_collections)
    assert sub.status_code == 201 and sub.data["expected_amount"] == "9000.00"
    assert set(Collection.objects.values_list("status", flat=True)) == {"SUBMITTED"}
    resp = approve(manager, sub.data["id"], "9000.00")
    assert resp.status_code == 200 and resp.data["status"] == "APPROVED" and resp.data["difference"] == "0.00"
    assert all(c.is_locked and c.status == "BRANCH_RECEIVED" for c in Collection.objects.all())
    assert not Discrepancy.objects.exists()


def test_shortage_requires_reason_and_creates_discrepancy(agent, manager, two_collections):
    sid = submit(agent, two_collections).data["id"]
    assert approve(manager, sid, "8500").data["code"] == "discrepancy_reason_required"
    resp = approve(manager, sid, "8500", note="Agent short by 500")
    assert resp.data["difference"] == "500.00"
    d = Discrepancy.objects.get()
    assert d.type == "SHORTAGE" and d.difference == Decimal("500.00")


def test_excess_cash_is_recorded(agent, manager, two_collections):
    sid = submit(agent, two_collections).data["id"]
    approve(manager, sid, "9100", note="Extra 100 found")
    assert Discrepancy.objects.get().type == "EXCESS"


def test_reject_returns_cash_to_agent_and_allows_resubmit(agent, manager, two_collections):
    sid = submit(agent, two_collections).data["id"]
    resp = client_for(manager).post(f"/api/submissions/{sid}/reject/", {"reason": "Notes torn"}, format="json")
    assert resp.data["status"] == "REJECTED"
    assert set(Collection.objects.values_list("status", flat=True)) == {"COLLECTED"}
    assert submit(agent, two_collections).status_code == 201


def test_cannot_submit_same_collection_twice(agent, two_collections):
    submit(agent, two_collections)
    assert submit(agent, two_collections).data["code"] == "invalid_collections"


def test_cannot_approve_twice(agent, manager, two_collections):
    sid = submit(agent, two_collections).data["id"]
    approve(manager, sid, "9000")
    assert approve(manager, sid, "9000").status_code == 409


def test_other_branch_manager_cannot_see_or_approve(agent, other_manager, two_collections):
    sid = submit(agent, two_collections).data["id"]
    assert approve(other_manager, sid, "9000").status_code == 404


def test_agent_cannot_approve(agent, two_collections):
    sid = submit(agent, two_collections).data["id"]
    assert approve(agent, sid, "9000").status_code == 403


def test_locked_collection_cannot_be_modified_even_via_orm(agent, manager, two_collections):
    sid = submit(agent, two_collections).data["id"]
    approve(manager, sid, "9000")
    c = Collection.objects.first()
    c.amount = Decimal("1.00")
    with pytest.raises(PermissionError):
        c.save()
    with pytest.raises(PermissionError):
        c.delete()


def test_reconciled_reversal_admin_only_and_flags_adjustment(agent, manager, admin_user, two_collections):
    sid = submit(agent, two_collections).data["id"]
    approve(manager, sid, "9000")
    cid = two_collections[0]
    assert client_for(manager).post(f"/api/collections/{cid}/reverse/", {"reason": "x"},
                                    format="json").status_code == 403
    resp = client_for(admin_user).post(f"/api/collections/{cid}/reverse/", {"reason": "Customer refund"},
                                       format="json")
    assert resp.status_code == 200
    assert Discrepancy.objects.get().type == "REVERSAL_ADJUSTMENT"


# --- Bank deposit & settlement -----------------------------------------------------------


@pytest.fixture
def approved_submission(agent, manager, two_collections):
    sid = submit(agent, two_collections).data["id"]
    approve(manager, sid, "8500", note="short 500")
    return sid


def deposit(manager, sids, amount, ref="UTR001", **extra):
    body = {"submission_ids": sids, "bank_name": "HDFC Bank", "account_number": "50100012345",
            "reference_number": ref, "deposit_date": timezone.localdate().isoformat(), "amount": amount, **extra}
    return client_for(manager).post("/api/deposits/", body, format="json")


def test_deposit_against_reconciled_cash(manager, approved_submission):
    resp = deposit(manager, [approved_submission], "8500")
    assert resp.status_code == 201
    assert resp.data["reconciled_amount"] == "8500.00" and resp.data["deposit_difference"] == "0.00"
    assert set(Collection.objects.values_list("status", flat=True)) == {"DEPOSITED"}


def test_deposit_mismatch_needs_reason(manager, approved_submission):
    assert deposit(manager, [approved_submission], "8000").data["code"] == "deposit_mismatch_reason_required"
    assert deposit(manager, [approved_submission], "8000", mismatch_reason="Fake note found").status_code == 201
    assert Discrepancy.objects.filter(type="BANK_MISMATCH", difference=Decimal("500.00")).exists()


def test_duplicate_bank_reference_rejected(manager, agent, loan, approved_submission):
    deposit(manager, [approved_submission], "8500", ref="utr 001")
    c = collect(agent, loan, "100").data["id"]
    sid = submit(agent, [c]).data["id"]
    approve(manager, sid, "100")
    resp = deposit(manager, [sid], "100", ref="UTR001")  # normalised to the same reference
    assert resp.status_code == 409 and resp.data["code"] == "duplicate_bank_reference"


def test_unapproved_submission_cannot_be_deposited(manager, agent, two_collections):
    sid = submit(agent, two_collections).data["id"]
    assert deposit(manager, [sid], "9000").data["code"] == "invalid_submissions"


def test_settlement_and_mismatch(manager, finance, approved_submission):
    dep = deposit(manager, [approved_submission], "8500").data
    c = client_for(finance)
    url = f"/api/deposits/{dep['id']}/settle/"
    body = {"settled_amount": "8400", "settled_on": timezone.localdate().isoformat(), "settlement_reference": "S1"}
    assert c.post(url, body, format="json").data["code"] == "settlement_mismatch_reason_required"
    resp = c.post(url, {**body, "note": "Bank charges"}, format="json")
    assert resp.data["status"] == "SETTLED" and resp.data["settlement_difference"] == "100.00"
    assert set(Collection.objects.values_list("status", flat=True)) == {"SETTLED"}
    assert Discrepancy.objects.filter(type="SETTLEMENT_MISMATCH").exists()
    assert c.post(url, {**body, "note": "x"}, format="json").status_code == 409


def test_manager_cannot_settle(manager, approved_submission):
    dep = deposit(manager, [approved_submission], "8500").data
    resp = client_for(manager).post(f"/api/deposits/{dep['id']}/settle/", {}, format="json")
    assert resp.status_code == 403


def test_failed_deposit_can_be_redeposited(manager, finance, approved_submission):
    dep = deposit(manager, [approved_submission], "8500").data
    resp = client_for(finance).post(f"/api/deposits/{dep['id']}/fail/", {"reason": "Cheque bounced"}, format="json")
    assert resp.data["status"] == "FAILED"
    assert set(Collection.objects.values_list("status", flat=True)) == {"BRANCH_RECEIVED"}
    assert deposit(manager, [approved_submission], "8500", ref="UTR002").status_code == 201


def test_delayed_settlement_flag(manager, approved_submission, settings):
    dep = deposit(manager, [approved_submission], "8500").data
    BankDeposit.objects.filter(pk=dep["id"]).update(deposit_date=timezone.localdate() - timedelta(days=5))
    assert [d.pk for d in flag_delayed_deposits()] == [dep["id"]]
    assert flag_delayed_deposits() == []  # only flagged once
    listed = client_for(manager).get("/api/deposits/?delayed=true").data
    assert listed["count"] == 1 and listed["results"][0]["is_delayed"] is True
