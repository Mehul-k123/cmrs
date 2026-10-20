from rest_framework.test import APIClient


def test_login_returns_tokens_and_profile(agent):
    resp = APIClient().post("/api/auth/login/", {"username": "agent", "password": "Passw0rd!x"}, format="json")
    assert resp.status_code == 200
    assert {"access", "refresh", "user"} <= set(resp.data)
    assert resp.data["user"]["role"] == "AGENT"


def test_bad_credentials(agent):
    resp = APIClient().post("/api/auth/login/", {"username": "agent", "password": "nope"}, format="json")
    assert resp.status_code == 401
    assert set(resp.data) == {"code", "message", "details"}


def test_unauthenticated_requests_rejected(db):
    assert APIClient().get("/api/collections/").status_code == 401


def test_logout_blacklists_refresh(agent):
    c = APIClient()
    tokens = c.post("/api/auth/login/", {"username": "agent", "password": "Passw0rd!x"}, format="json").data
    c.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
    assert c.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401
