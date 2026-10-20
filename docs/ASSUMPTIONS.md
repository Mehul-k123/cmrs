# Assumptions & Business Rules

Where the brief did not define behaviour, these are the decisions made, with the reason for each.

## Roles

| Role | Scope | Rationale |
|---|---|---|
| **Admin** | Organisation-wide | Master data (branches, users, customers, loans). Sole authority to reverse a *reconciled* collection. |
| **Finance** | Organisation-wide | Owns bank-statement reconciliation (settle / fail deposits), audit log, UPI gateway settlement. Has no cash-handling rights, which keeps duties separate from branch staff. |
| **Branch Manager** | Own branch | Creates customers and loans for the branch, verifies agent cash, records discrepancies, creates bank deposits. Cannot settle their own deposits. |
| **Collection Agent** | Assigned customers only | Records repayments for customers assigned to them, views daily collections, submits cash. |

Scoping is enforced on the server for every list and detail endpoint (`scope_queryset`). A record outside a user's scope returns **404**, not 403, so its existence isn't leaked. A permitted record with a forbidden action returns **403**.

## Loans & schedules

- **Flat interest**: `interest = principal × rate × tenure/12`. EMIs are equal and rounded **down** to the paisa, and the final EMI absorbs the remainder, so the schedule always sums exactly to principal + interest.
- First EMI falls due one month after disbursal; month-end dates clamp (31 Jan → 28 Feb).
- Loan **outstanding** = Σ(installment due − paid). It is computed from the schedule, never stored, so it cannot drift.
- A loan auto-closes when outstanding reaches 0 and re-opens if a reversal restores a balance.
- No penal interest or late fees. *Overdue* = unpaid installment past its due date (display only).

## Collections

| Case | Rule |
|---|---|
| **Partial repayment** | Allowed. Applied **oldest unpaid installment first** (`CollectionAllocation` rows record the split). An installment becomes `PARTIAL` or `PAID`. |
| **Over-collection** | **Rejected** (400 `over_collection`) when the amount exceeds the loan's outstanding. Cash agents shouldn't hold customer money they can't apply; advance payments and refunds are out of scope. |
| **Duplicate (technical)** | `Idempotency-Key` header is **required**. The frontend creates one UUID per form, so a double-click or network retry returns the **same receipt** (200), never a second one. Reusing a key with a different payload returns 409. |
| **Duplicate (business)** | Same loan + same amount within `DUPLICATE_COLLECTION_WINDOW_MINUTES` (default 10) returns 409 `possible_duplicate` with the earlier receipt number. The agent can confirm (`confirm_duplicate=true`), and the confirmation is audit-logged. |
| **Receipt numbers** | `RCP-<BRANCH>-<YYYYMMDD>-<seq>` from a Postgres sequence, plus a unique constraint. Sequences are gap-tolerant; gaps after rollbacks are acceptable for receipts. |
| **Who can collect** | Only the customer's **assigned agent**. Branch walk-in cash counters are out of scope. |
| **Back-dating** | `collected_at` may be supplied (offline entry) but not in the future. |
| **Edits / deletes** | No update or delete endpoints exist. Corrections happen only through **reversal**. |

## Cash submission & branch reconciliation

- An agent submits any subset of their `COLLECTED` **cash** collections. *Expected* = their sum; *declared* = what the agent says they handed over.
- The branch manager enters **received** (counted) cash. `difference = expected − received` (positive = shortage, matching the brief's example: 50,000 − 48,500 = 1,500).
- `difference ≠ 0` requires a reason. The submission is **approved at the received amount**, and a `SHORTAGE` or `EXCESS` **Discrepancy** is opened against the agent. Recovering the shortage from the agent is a manual process, closed by resolving the discrepancy.
- **Rejection** (reason required) puts the collections back to `COLLECTED`: the agent still holds the cash and can resubmit. Rejected submissions are kept for history.
- A manager cannot review their own submission. Double approval returns 409 because the row is locked with `SELECT … FOR UPDATE`.
- **Approval locks** every collection in the submission (`is_locked`). See *Unauthorized modification* below.

## Bank deposit & settlement

- Only `APPROVED` submissions of the manager's own branch can be deposited. *Reconciled* = Σ received amounts.
- Deposit amount ≠ reconciled requires a reason and opens a `BANK_MISMATCH` discrepancy (for example, a counterfeit note rejected at the counter).
- **Duplicate bank reference**: references are normalised (whitespace removed, upper-cased) and are unique per bank (DB constraint plus a friendly 409).
- Deposit date cannot be in the future.
- **Settlement** is confirmed by **Finance** against the bank statement. A settled amount ≠ deposited amount requires a reason and opens a `SETTLEMENT_MISMATCH` discrepancy (for example, bank charges).
- **Failed settlement**: Finance marks the deposit `FAILED` with a reason. Its submissions return to `APPROVED` (cash back at branch) and can be re-deposited under a **new** reference.
- **Delayed settlement**: a deposit still `DEPOSITED` after `SETTLEMENT_SLA_DAYS` (default 2) shows as *delayed* in lists and the dashboard. The `flag_delayed_settlements` command (schedule daily via cron; a Render cron block is included in `render.yaml`) stamps `delay_flagged_at` once and writes an audit entry.

## Unauthorized modification of reconciled transactions

Defence in depth:
1. **API**: no PUT, PATCH or DELETE on collections, submissions, deposits or discrepancies. State changes happen only through explicit action endpoints with role checks.
2. **Model**: `Collection.save()` raises if any financial field changes on a locked row; `delete()` always raises. `AuditLog` is append-only the same way.
3. **Django admin**: financial models are read-only there.
4. **Reversal of a reconciled collection** is Admin-only, needs a reason, restores the loan balance, and opens a `REVERSAL_ADJUSTMENT` discrepancy so Finance can follow up on money that has already been banked.
5. Every transition writes an **AuditLog** row (actor, before/after, IP, request id).

## Digital (UPI) payments, via a mock gateway

- The `MockGateway` stands in for Razorpay or Cashfree. A payment intent is created for an amount ≤ outstanding. A signed (`HMAC-SHA256`) webhook `payment.captured` creates a `UPI` collection with **no agent**, locked from the start, allocated like cash.
- The webhook is idempotent on `event_id`. The captured amount must equal the requested amount, otherwise the intent fails (tamper protection). If the loan was paid off in cash in the meantime, the capture is rejected as over-collection and flagged *refund required*.
- `settlement.processed` moves the UPI collections straight to `SETTLED`. Digital money never touches agent or branch custody, but it shares the loan ledger and the dashboard totals.

## Dashboard definitions

All figures respect the date range, branch, agent and status filters. Branch managers are forced to their own branch and agents to themselves.

| KPI | Definition |
|---|---|
| Expected | Σ installment `amount_due` with due date in the range |
| Total collected | Σ non-reversed collections with `collected_at` in the range (cash + UPI) |
| Cash held by agents | Σ cash collections in status `COLLECTED` + `SUBMITTED` |
| Received at branches | Σ `received_amount` of submissions reviewed in the range and approved |
| Awaiting bank deposit | Σ `received_amount` of currently `APPROVED` submissions (point in time) |
| Bank deposits | Σ deposits in the range, excluding failed |
| Settled | Σ bank-credited amounts + settled UPI |
| Outstanding / overdue | Point in time across active loans in scope |
| Discrepancies | Open count and Σ\|difference\|, by type |

## Out of scope (deliberately)

Customer self-service login, multi-currency, interest recalculation, penal charges, refunds, agent route planning, and real bank-statement file import (settlement is entered manually by Finance).
