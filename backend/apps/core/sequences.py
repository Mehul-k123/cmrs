"""Human-readable, gap-tolerant unique reference numbers backed by Postgres sequences."""

from django.db import connection
from django.utils import timezone


def next_value(sequence_name: str) -> int:
    with connection.cursor() as cur:
        cur.execute(f'CREATE SEQUENCE IF NOT EXISTS "{sequence_name}"')
        cur.execute("SELECT nextval(%s)", [sequence_name])
        return cur.fetchone()[0]


def make_reference(prefix: str, branch_code: str | None = None) -> str:
    """e.g. RCP-MUM-20261017-000042. Sequence is global per prefix so numbers never collide."""
    seq = next_value(f"cmrs_seq_{prefix.lower()}")
    parts = [prefix]
    if branch_code:
        parts.append(branch_code)
    parts += [timezone.localdate().strftime("%Y%m%d"), f"{seq:06d}"]
    return "-".join(parts)
