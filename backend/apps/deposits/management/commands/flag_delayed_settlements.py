from django.core.management.base import BaseCommand

from apps.deposits.services import flag_delayed_deposits


class Command(BaseCommand):
    help = "Flag bank deposits that have not settled within SETTLEMENT_SLA_DAYS."

    def handle(self, *args, **options):
        delayed = flag_delayed_deposits()
        for d in delayed:
            self.stdout.write(f"Delayed: {d.deposit_number} ({d.branch.code}) deposited {d.deposit_date}")
        self.stdout.write(self.style.SUCCESS(f"{len(delayed)} deposit(s) newly flagged as delayed."))
