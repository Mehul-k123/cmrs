"""Create demo branches, users (one per role), customers, loans and a realistic spread of collections
through every lifecycle state. All data goes through the same service layer as the API, so the
business rules (allocation, discrepancies, locking, audit) are applied exactly as in production."""

import random
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.cash import services as cash
from apps.cash.models import CashSubmission, Collection
from apps.core.models import Branch
from apps.core.permissions import Role
from apps.deposits import services as deposits
from apps.deposits.models import BankDeposit
from apps.loans.models import Customer
from apps.loans.services import add_months, create_loan
from apps.payments import services as payments

PASSWORD = "Demo@1234"

AGENTS = {
    "MUM": [("agent.ravi", "Ravi", "Kumar"), ("agent.priya", "Priya", "Sharma")],
    "PUN": [("agent.arjun", "Arjun", "Patil"), ("agent.sneha", "Sneha", "Kulkarni")],
}
CUSTOMER_NAMES = [
    "Aarav Mehta", "Diya Nair", "Kabir Singh", "Meera Iyer", "Rohan Das", "Ananya Rao", "Vihaan Joshi",
    "Isha Gupta", "Aditya Verma", "Saanvi Reddy", "Arnav Pillai", "Kavya Menon", "Reyansh Shah", "Tara Bose",
    "Yash Chauhan", "Nisha Pawar", "Dev Malhotra", "Pooja Desai", "Kunal Jain", "Riya Kapoor",
]


class Command(BaseCommand):
    help = "Seed demo data. Use --reset to wipe the database first."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Flush ALL data before seeding")
        parser.add_argument("--if-empty", action="store_true", help="Seed only when there are no users (safe on boot)")

    def handle(self, *args, reset=False, if_empty=False, **options):
        if if_empty and User.objects.exists():
            self.stdout.write("Users exist; skipping demo seed.")
            return
        if reset:
            call_command("flush", interactive=False, verbosity=0)
        elif User.objects.exists():
            raise CommandError("Database already has users. Re-run with --reset to wipe and reseed.")
        random.seed(42)
        with transaction.atomic():
            self._seed()
        self.stdout.write(self.style.SUCCESS(f"Demo data created. All users have password: {PASSWORD}"))

    # -- helpers ---------------------------------------------------------------------

    def _user(self, username, role, branch=None, first="", last="", **extra):
        u = User(username=username, role=role, branch=branch, first_name=first, last_name=last,
                 email=f"{username}@cmrs.demo", **extra)
        u.set_password(PASSWORD)
        u.save()
        return u

    def _at(self, days_ago: int, hour: int = 11) -> datetime:
        d = timezone.localdate() - timedelta(days=days_ago)
        return min(timezone.make_aware(datetime.combine(d, time(hour, random.randint(0, 59)))), timezone.now())

    def _collect(self, agent, loan, amount, days_ago):
        col, _ = cash.record_cash_collection(
            agent=agent, loan_id=loan.pk, amount=Decimal(amount), idempotency_key=uuid.uuid4().hex,
            collected_at=self._at(days_ago, random.randint(9, 17)), confirm_duplicate=True,
        )
        return col

    def _backdate_submission(self, sub, days_ago):
        sub.refresh_from_db()
        CashSubmission.objects.filter(pk=sub.pk).update(
            submitted_at=self._at(days_ago, 18), reviewed_at=self._at(days_ago, 19) if sub.reviewed_by_id else None
        )

    # -- scenario ----------------------------------------------------------------------

    def _seed(self):
        mum = Branch.objects.create(code="MUM", name="Mumbai Central", address="Lamington Road, Mumbai")
        pun = Branch.objects.create(code="PUN", name="Pune Camp", address="MG Road, Pune")
        branches = {"MUM": mum, "PUN": pun}

        admin = self._user("admin", Role.ADMIN, first="System", last="Admin", is_staff=True, is_superuser=True)
        finance = self._user("finance", Role.FINANCE, first="Farah", last="Khan")
        managers = {
            "MUM": self._user("bm.mumbai", Role.BRANCH_MANAGER, mum, "Suresh", "Iyer"),
            "PUN": self._user("bm.pune", Role.BRANCH_MANAGER, pun, "Neha", "Joshi"),
        }
        agents = {code: [self._user(u, Role.AGENT, branches[code], f, ln) for u, f, ln in rows]
                  for code, rows in AGENTS.items()}

        # 5 customers per agent, one loan each, disbursed 2–5 months ago
        loans_by_agent: dict[str, list] = {}
        names = iter(CUSTOMER_NAMES)
        today = timezone.localdate()
        for code, branch_agents in agents.items():
            for agent in branch_agents:
                loans_by_agent[agent.username] = []
                for i in range(5):
                    customer = Customer.objects.create(
                        customer_code=f"CUST-{code}-{agent.pk:02d}{i:02d}", name=next(names),
                        phone=f"98{random.randint(10000000, 99999999)}", address=f"{code} locality {i + 1}",
                        branch=branches[code], assigned_agent=agent,
                    )
                    disbursed = add_months(today, -random.randint(2, 5))
                    loan = create_loan(
                        actor=admin, customer=customer,
                        principal=Decimal(random.choice([25000, 40000, 50000, 60000, 75000, 100000])),
                        interest_rate=Decimal(random.choice(["12.00", "14.50", "18.00", "21.00"])),
                        tenure_months=12, disbursed_on=disbursed,
                    )
                    loans_by_agent[agent.username].append(loan)

        def emi(loan):
            return loan.installments.order_by("number").first().amount_due

        ravi, priya = agents["MUM"]
        arjun, sneha = agents["PUN"]
        bm_mum, bm_pun = managers["MUM"], managers["PUN"]

        # 1) Ravi: full EMIs 20 days ago → approved exactly → deposited → settled
        cols = [self._collect(ravi, ln, emi(ln), 20) for ln in loans_by_agent["agent.ravi"][:4]]
        sub = cash.create_submission(agent=ravi, collection_ids=[c.pk for c in cols], declared_amount=None)
        cash.approve_submission(reviewer=bm_mum, submission_id=sub.pk, received_amount=sub.expected_amount)
        self._backdate_submission(sub, 20)
        dep = deposits.create_deposit(
            actor=bm_mum, branch=mum, submission_ids=[sub.pk], bank_name="HDFC Bank", account_number="50200011112222",
            reference_number="HDFC-UTR-880011", deposit_date=today - timedelta(days=19), amount=sub.expected_amount)
        deposits.settle_deposit(actor=finance, deposit_id=dep.pk, settled_amount=dep.amount,
                                settled_on=today - timedelta(days=18), settlement_reference="STMT-0918")

        # 2) Priya: partial payments 14 days ago → cash shortage of ₹500 → deposit mismatch → settled
        cols = [self._collect(priya, ln, (emi(ln) / 2).quantize(Decimal("1")), 14)
                for ln in loans_by_agent["agent.priya"][:3]]
        cols.append(self._collect(priya, loans_by_agent["agent.priya"][3], emi(loans_by_agent["agent.priya"][3]), 14))
        sub = cash.create_submission(agent=priya, collection_ids=[c.pk for c in cols], declared_amount=None)
        received = sub.expected_amount - Decimal("500")
        cash.approve_submission(reviewer=bm_mum, submission_id=sub.pk, received_amount=received,
                                note="Cash short by ₹500 at counting; agent to explain")
        self._backdate_submission(sub, 13)
        dep = deposits.create_deposit(
            actor=bm_mum, branch=mum, submission_ids=[sub.pk], bank_name="HDFC Bank", account_number="50200011112222",
            reference_number="HDFC-UTR-880245", deposit_date=today - timedelta(days=12),
            amount=received - Decimal("200"), mismatch_reason="₹200 counterfeit note rejected by bank teller")
        deposits.settle_deposit(actor=finance, deposit_id=dep.pk, settled_amount=dep.amount,
                                settled_on=today - timedelta(days=11), settlement_reference="STMT-0925")

        # 3) Arjun: submission rejected (count mismatch) → resubmitted → approved → deposited, settlement delayed
        cols = [self._collect(arjun, ln, emi(ln), 9) for ln in loans_by_agent["agent.arjun"][:3]]
        sub = cash.create_submission(agent=arjun, collection_ids=[c.pk for c in cols],
                                     declared_amount=sum(c.amount for c in cols) - Decimal("1000"))
        cash.reject_submission(reviewer=bm_pun, submission_id=sub.pk,
                               reason="Declared amount does not match collections; recount and resubmit")
        self._backdate_submission(sub, 9)
        sub = cash.create_submission(agent=arjun, collection_ids=[c.pk for c in cols], declared_amount=None)
        cash.approve_submission(reviewer=bm_pun, submission_id=sub.pk, received_amount=sub.expected_amount)
        self._backdate_submission(sub, 8)
        deposits.create_deposit(
            actor=bm_pun, branch=pun, submission_ids=[sub.pk], bank_name="ICICI Bank", account_number="00340500998877",
            reference_number="ICICI-TXN-551203", deposit_date=today - timedelta(days=7), amount=sub.expected_amount)
        deposits.flag_delayed_deposits()

        # 4) Sneha: approved with excess cash → deposit failed (bank returned) → awaiting re-deposit
        cols = [self._collect(sneha, ln, emi(ln), 5) for ln in loans_by_agent["agent.sneha"][:3]]
        sub = cash.create_submission(agent=sneha, collection_ids=[c.pk for c in cols], declared_amount=None)
        sub = cash.approve_submission(reviewer=bm_pun, submission_id=sub.pk, received_amount=sub.expected_amount + 100,
                                note="₹100 extra found in bundle")
        self._backdate_submission(sub, 5)
        dep = deposits.create_deposit(
            actor=bm_pun, branch=pun, submission_ids=[sub.pk], bank_name="ICICI Bank", account_number="00340500998877",
            reference_number="ICICI-TXN-551977", deposit_date=today - timedelta(days=4),
            amount=sub.received_amount)
        deposits.fail_deposit(actor=finance, deposit_id=dep.pk, reason="Bank CDM error — deposit reversed by bank")

        # 5) Recent activity: submitted & pending verification, and cash still with agents
        cols = [self._collect(ravi, ln, emi(ln), 1) for ln in loans_by_agent["agent.ravi"][4:]]
        cols.append(self._collect(ravi, loans_by_agent["agent.ravi"][0], Decimal("1500"), 1))
        sub = cash.create_submission(agent=ravi, collection_ids=[c.pk for c in cols], declared_amount=None,
                                     note="Evening handover")
        CashSubmission.objects.filter(pk=sub.pk).update(submitted_at=self._at(1, 18))
        self._collect(priya, loans_by_agent["agent.priya"][4], emi(loans_by_agent["agent.priya"][4]), 0)
        self._collect(priya, loans_by_agent["agent.priya"][0], Decimal("2000"), 0)
        for ln in loans_by_agent["agent.arjun"][3:]:
            self._collect(arjun, ln, emi(ln), 0)
        self._collect(sneha, loans_by_agent["agent.sneha"][3], Decimal("1200"), 2)

        # 6) A mistaken entry reversed before submission
        wrong = self._collect(sneha, loans_by_agent["agent.sneha"][4], Decimal("999"), 0)
        cash.reverse_collection(actor=bm_pun, collection_id=wrong.pk, reason="Entered on wrong loan account")

        # 7) Digital (UPI) repayments via the mock gateway: one settled, one captured, one failed
        for idx, outcome in enumerate(["success", "success", "failure"]):
            loan = loans_by_agent["agent.arjun"][idx]
            intent, _ = payments.create_intent(actor=arjun, loan_id=loan.pk, amount=Decimal("2500"))
            payments.simulate_payment(intent, success=outcome == "success")
            if idx == 0:
                payments.simulate_settlement()

        self.stdout.write(
            f"Branches: {Branch.objects.count()}  Users: {User.objects.count()}  "
            f"Customers: {Customer.objects.count()}  Collections: {Collection.objects.count()}  "
            f"Deposits: {BankDeposit.objects.count()}"
        )
