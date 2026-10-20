/** Monetary values are always decimal strings from the API (e.g. "1500.50"). Never parse to float for math. */
export type Money = string;

export type Role = "ADMIN" | "FINANCE" | "BRANCH_MANAGER" | "AGENT";

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  display_name: string;
  email: string;
  phone: string;
  role: Role;
  branch: number | null;
  branch_name: string | null;
  is_active: boolean;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Branch {
  id: number;
  code: string;
  name: string;
  address: string;
  is_active: boolean;
}

export interface Customer {
  id: number;
  customer_code: string;
  name: string;
  phone: string;
  address: string;
  branch: number;
  branch_name: string;
  assigned_agent: number | null;
  assigned_agent_name: string | null;
  active_loans: number;
  created_at: string;
}

export interface Loan {
  id: number;
  loan_number: string;
  customer: number;
  customer_name: string;
  customer_code: string;
  branch: number;
  branch_name: string;
  principal: Money;
  interest_rate: string;
  tenure_months: number;
  disbursed_on: string;
  status: "ACTIVE" | "CLOSED";
  total_due: Money;
  total_paid: Money;
  outstanding: Money;
  next_due_date: string | null;
}

export interface Installment {
  id: number;
  number: number;
  due_date: string;
  amount_due: Money;
  amount_paid: Money;
  balance: Money;
  status: "PENDING" | "PARTIAL" | "PAID";
  is_overdue: boolean;
}

export type CollectionStatus =
  | "COLLECTED"
  | "SUBMITTED"
  | "BRANCH_RECEIVED"
  | "DEPOSITED"
  | "SETTLED"
  | "REVERSED";

export interface Collection {
  id: number;
  receipt_number: string;
  loan: number;
  loan_number: string;
  customer: number;
  customer_name: string;
  branch: number;
  branch_name: string;
  agent: number | null;
  agent_name: string | null;
  amount: Money;
  mode: "CASH" | "UPI";
  status: CollectionStatus;
  collected_at: string;
  payment_reference: string;
  notes: string;
  is_locked: boolean;
  reversed_at: string | null;
  reversal_reason: string;
  allocations?: { installment_number: number; due_date: string; amount: Money }[];
}

export type SubmissionStatus = "SUBMITTED" | "APPROVED" | "REJECTED" | "DEPOSITED" | "SETTLED";

export interface Submission {
  id: number;
  submission_number: string;
  agent: number;
  agent_name: string;
  branch: number;
  branch_name: string;
  expected_amount: Money;
  declared_amount: Money;
  received_amount: Money | null;
  difference: Money | null;
  status: SubmissionStatus;
  submitted_at: string;
  agent_note: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_note: string;
  item_count: number | null;
  items?: {
    collection: number;
    receipt_number: string;
    customer_name: string;
    loan_number: string;
    collected_at: string;
    amount: Money;
  }[];
}

export interface Discrepancy {
  id: number;
  type: "SHORTAGE" | "EXCESS" | "BANK_MISMATCH" | "SETTLEMENT_MISMATCH" | "REVERSAL_ADJUSTMENT";
  status: "OPEN" | "RESOLVED";
  branch: number;
  branch_name: string;
  agent_name: string | null;
  submission_number: string | null;
  deposit_number: string | null;
  receipt_number: string | null;
  expected_amount: Money;
  actual_amount: Money;
  difference: Money;
  reason: string;
  raised_by_name: string;
  created_at: string;
  resolved_by_name: string | null;
  resolved_at: string | null;
  resolution_note: string;
}

export interface Deposit {
  id: number;
  deposit_number: string;
  branch: number;
  branch_name: string;
  bank_name: string;
  account_number: string;
  reference_number: string;
  deposit_date: string;
  reconciled_amount: Money;
  amount: Money;
  deposit_difference: Money;
  status: "DEPOSITED" | "SETTLED" | "FAILED";
  mismatch_reason: string;
  created_by_name: string;
  settled_amount: Money | null;
  settled_on: string | null;
  settlement_reference: string;
  settled_by_name: string | null;
  settlement_difference: Money | null;
  failure_reason: string;
  is_delayed: boolean;
  submissions?: Submission[];
}

export interface PaymentIntent {
  id: number;
  intent_number: string;
  gateway_ref: string;
  loan: number;
  loan_number: string;
  customer_name: string;
  amount: Money;
  status: "CREATED" | "PAID" | "FAILED" | "SETTLED";
  receipt_number: string | null;
  failure_reason: string;
  created_at: string;
  payment_url?: string;
}

export interface AuditEntry {
  id: number;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface DashboardSummary {
  filters: { date_from: string; date_to: string; branch: number | null; agent: number | null; status: string | null };
  kpis: Record<string, Money | number | null>;
  lifecycle: Record<CollectionStatus, Money>;
  trend: { date: string; cash: Money; digital: Money }[];
  by_branch: { branch_id: number; branch: string; collected: Money; cash_with_agents: Money; count: number }[];
  by_agent: {
    agent_id: number;
    agent: string;
    collected: Money;
    cash_in_hand: Money;
    pending_verification: Money;
    shortages: Money;
    count: number;
  }[];
  discrepancies_by_type: { type: string; count: number; amount: Money }[];
}

export interface ApiError {
  code: string;
  message: string;
  details: unknown;
}
