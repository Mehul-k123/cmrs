import uuid
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.models import Branch
from apps.core.permissions import Role
from apps.loans.models import Customer
from apps.loans.services import create_loan


@pytest.fixture
def branch(db):
    return Branch.objects.create(code="MUM", name="Mumbai")


@pytest.fixture
def other_branch(db):
    return Branch.objects.create(code="PUN", name="Pune")


def _user(username, role, branch=None):
    return User.objects.create_user(username=username, password="Passw0rd!x", role=role, branch=branch)


@pytest.fixture
def admin_user(db):
    return _user("admin", Role.ADMIN)


@pytest.fixture
def finance(db):
    return _user("finance", Role.FINANCE)


@pytest.fixture
def manager(branch):
    return _user("bm", Role.BRANCH_MANAGER, branch)


@pytest.fixture
def other_manager(other_branch):
    return _user("bm2", Role.BRANCH_MANAGER, other_branch)


@pytest.fixture
def agent(branch):
    return _user("agent", Role.AGENT, branch)


@pytest.fixture
def other_agent(branch):
    return _user("agent2", Role.AGENT, branch)


@pytest.fixture
def customer(branch, agent):
    return Customer.objects.create(customer_code="C1", name="Asha", phone="9999999999", branch=branch,
                                   assigned_agent=agent)


@pytest.fixture
def loan(customer, admin_user):
    # 12,000 principal, 0% → 12 installments of 1,000.00
    return create_loan(actor=admin_user, customer=customer, principal=Decimal("12000"), interest_rate=Decimal("0"),
                       tenure_months=12, disbursed_on=date(2026, 1, 1))


def client_for(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user)
    return c


def collect(user, loan, amount, key=None, **extra):
    return client_for(user).post(
        "/api/collections/", {"loan": loan.pk, "amount": str(amount), **extra}, format="json",
        HTTP_IDEMPOTENCY_KEY=key or uuid.uuid4().hex,
    )
