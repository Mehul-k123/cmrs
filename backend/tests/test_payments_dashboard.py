import json
from decimal import Decimal

from apps.cash.models import Collection
from apps.payments.gateway import gateway, sign

from .conftest import client_for, collect


def test_upi_payment_flow_and_settlement(loan, agent, finance):
    c = client_for(agent)
    intent = c.post("/api/payments/intents/", {"loan": loan.pk, "amount": "2000"}, format="json").data
    assert intent["status"] == "CREATED"
    paid = c.post(f"/api/payments/intents/{intent['id']}/simulate/", {"outcome": "success"}, format="json").data
    assert paid["status"] == "PAID" and paid["receipt_number"].startswith("UPI-")
    col = Collection.objects.get(mode="UPI")
    assert col.agent is None and col.is_locked
    assert loan.compute_totals()["outstanding"] == Decimal("10000.00")
    client_for(finance).post("/api/payments/intents/simulate-settlement/", format="json")
    col.refresh_from_db()
    assert col.status == "SETTLED"


def test_webhook_rejects_bad_signature(client, db):
    resp = client.post("/api/payments/webhook/", data=json.dumps({"id": "e", "type": "x", "data": {}}),
                       content_type="application/json", HTTP_X_SIGNATURE="bad")
    assert resp.status_code == 401


def test_webhook_is_idempotent(loan, agent):
    intent = client_for(agent).post("/api/payments/intents/", {"loan": loan.pk, "amount": "500"}, format="json").data
    body = json.dumps({"id": "evt_same", "type": "payment.captured",
                       "data": {"gateway_ref": intent["gateway_ref"], "amount": "500.00"}}).encode()
    from django.test import Client

    for _ in range(2):
        Client().post("/api/payments/webhook/", data=body, content_type="application/json",
                      HTTP_X_SIGNATURE=sign(body))
    assert Collection.objects.filter(mode="UPI").count() == 1


def test_webhook_amount_tampering_rejected(loan, agent):
    intent = client_for(agent).post("/api/payments/intents/", {"loan": loan.pk, "amount": "500"}, format="json").data
    from apps.payments.services import handle_webhook

    body, sig = gateway.build_event("payment.captured", {"gateway_ref": intent["gateway_ref"], "amount": "5"})
    assert handle_webhook(body, sig)["status"] == "amount_mismatch"
    assert not Collection.objects.exists()


def test_dashboard_totals_follow_lifecycle(loan, agent, manager, admin_user):
    collect(agent, loan, "1000")
    cid = collect(agent, loan, "2500").data["id"]
    k = client_for(admin_user).get("/api/dashboard/summary/").data["kpis"]
    assert k["total_collected"] == "3500.00" and k["cash_with_agents"] == "3500.00"
    sid = client_for(agent).post("/api/submissions/", {"collection_ids": [cid]}, format="json").data["id"]
    client_for(manager).post(f"/api/submissions/{sid}/approve/", {"received_amount": "2400", "note": "short"},
                             format="json")
    k = client_for(manager).get("/api/dashboard/summary/").data["kpis"]
    assert k["cash_with_agents"] == "1000.00"
    assert k["received_at_branches"] == "2400.00"
    assert k["awaiting_bank_deposit"] == "2400.00"
    assert k["open_discrepancies"] == 1 and k["open_discrepancy_amount"] == "100.00"
    assert k["outstanding_amount"] == "8500.00"


def test_dashboard_is_scoped_for_agents(loan, agent, other_agent):
    collect(agent, loan, "1000")
    k = client_for(other_agent).get(f"/api/dashboard/summary/?agent={agent.pk}").data["kpis"]
    assert k["total_collected"] == "0.00"


def test_audit_log_restricted(agent, finance, loan):
    assert client_for(agent).get("/api/audit-logs/").status_code == 403
    assert client_for(finance).get("/api/audit-logs/").data["count"] >= 1
