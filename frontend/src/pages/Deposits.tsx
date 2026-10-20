import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus } from "lucide-react";
import { useState } from "react";

import { api, errorText } from "../api/client";
import type { Deposit, Submission } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Filters, type FilterValues } from "../components/Filters";
import { Alert, Amount, Button, Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table } from "../components/ui";
import { formatDate, formatINR, todayISO } from "../lib/format";
import { useList } from "../lib/hooks";
import { compare, isValidAmount, subtract, sumMoney } from "../lib/money";

const STATUSES: [string, string][] = [["DEPOSITED", "Awaiting settlement"], ["SETTLED", "Settled"], ["FAILED", "Failed"]];

export default function DepositsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<FilterValues>({});
  const [delayed, setDelayed] = useState(false);
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [settling, setSettling] = useState<Deposit | null>(null);
  const { data, isLoading } = useList<Deposit>("/deposits/", { ...filters, delayed: delayed || undefined, page });
  const isFinance = user?.role === "FINANCE" || user?.role === "ADMIN";

  return (
    <div>
      <PageHeader title="Bank deposits & settlement"
        subtitle="Branch-reconciled cash deposited into the company account, and its settlement against the bank statement."
        actions={user?.role === "BRANCH_MANAGER" && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New bank deposit</Button>} />
      <Filters value={filters} onChange={(v) => { setFilters(v); setPage(1); }} statuses={STATUSES} showAgent={false}>
        <label className="flex items-center gap-2 pb-2 text-sm text-slate-600">
          <input type="checkbox" checked={delayed} onChange={(e) => setDelayed(e.target.checked)} className="h-4 w-4 rounded border-slate-300" /> Delayed only
        </label>
      </Filters>
      <Card padded={false}>
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={
            <tr><th className="th">Deposit</th><th className="th">Bank / Ref</th><th className="th">Date</th><th className="th num">Reconciled</th><th className="th num">Deposited</th><th className="th num">Settled</th><th className="th">Status</th><th className="th" /></tr>
          }>
            {data?.results.map((d) => (
              <tr key={d.id} className="align-top hover:bg-slate-50">
                <td className="td font-mono text-xs">{d.deposit_number}<div className="font-sans text-slate-400">{d.branch_name}</div></td>
                <td className="td">{d.bank_name}<div className="font-mono text-xs text-slate-400">{d.reference_number}</div></td>
                <td className="td">{formatDate(d.deposit_date)}{d.settled_on && <div className="text-xs text-slate-400">settled {formatDate(d.settled_on)}</div>}</td>
                <td className="td num"><Amount value={d.reconciled_amount} /></td>
                <td className="td num"><Amount value={d.amount} />
                  {Number(d.deposit_difference) !== 0 && <div className="text-xs"><Amount value={d.deposit_difference} signed /></div>}</td>
                <td className="td num"><Amount value={d.settled_amount} />
                  {d.settlement_difference && Number(d.settlement_difference) !== 0 && <div className="text-xs"><Amount value={d.settlement_difference} signed /></div>}</td>
                <td className="td">
                  <div className="flex flex-col items-start gap-1">
                    <StatusBadge status={d.status} />
                    {d.is_delayed && <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700"><AlertTriangle className="h-3 w-3" /> Delayed</span>}
                    {d.failure_reason && <span className="max-w-[12rem] whitespace-normal text-xs text-rose-600">{d.failure_reason}</span>}
                  </div>
                </td>
                <td className="td text-right">{isFinance && d.status === "DEPOSITED" && <Button onClick={() => setSettling(d)}>Reconcile</Button>}</td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
      {creating && <CreateDeposit onClose={() => setCreating(false)} />}
      {settling && <SettleModal d={settling} onClose={() => setSettling(null)} />}
    </div>
  );
}

function CreateDeposit({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const subs = useList<Submission>("/submissions/", { status: "APPROVED", page_size: 200 });
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [form, setForm] = useState({ bank_name: "HDFC Bank", account_number: "", reference_number: "", deposit_date: todayISO(), amount: "", mismatch_reason: "" });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const rows = subs.data?.results ?? [];
  const reconciled = sumMoney(rows.filter((s) => picked.has(s.id)).map((s) => s.received_amount ?? "0"));
  const amount = form.amount || reconciled;
  const diff = isValidAmount(amount) ? subtract(reconciled, amount) : null;
  const mismatch = diff !== null && compare(diff, "0") !== 0;

  const m = useMutation({
    mutationFn: () => api.post("/deposits/", { ...form, amount, submission_ids: [...picked] }),
    onSuccess: () => { qc.invalidateQueries(); onClose(); },
  });
  const toggle = (id: number) => setPicked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const ok = picked.size > 0 && form.account_number && form.reference_number && isValidAmount(amount) && (!mismatch || form.mismatch_reason.trim());

  return (
    <Modal open wide onClose={onClose} title="New bank deposit" footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button loading={m.isPending} disabled={!ok} onClick={() => m.mutate()}>Record deposit</Button>
    </>}>
      <div>
        <p className="label">Approved submissions awaiting deposit</p>
        {subs.isLoading ? <Spinner /> : rows.length === 0 ? <Alert kind="info">No approved cash is waiting to be deposited.</Alert> : (
          <div className="max-h-52 overflow-y-auto rounded-lg border border-slate-100">
            {rows.map((s) => (
              <label key={s.id} className="flex cursor-pointer items-center gap-3 border-b border-slate-100 px-3 py-2 text-sm last:border-0 hover:bg-slate-50">
                <input type="checkbox" checked={picked.has(s.id)} onChange={() => toggle(s.id)} className="h-4 w-4 rounded border-slate-300" />
                <span className="font-mono text-xs">{s.submission_number}</span>
                <span className="text-slate-500">{s.agent_name}</span>
                <span className="ml-auto font-medium tabular-nums">{formatINR(s.received_amount)}</span>
              </label>
            ))}
          </div>
        )}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Bank"><input className="input" value={form.bank_name} onChange={set("bank_name")} /></Field>
        <Field label="Account number"><input className="input" value={form.account_number} onChange={set("account_number")} /></Field>
        <Field label="Transaction / slip reference" hint="Must be unique per bank."><input className="input font-mono" value={form.reference_number} onChange={set("reference_number")} /></Field>
        <Field label="Deposit date"><input type="date" className="input" max={todayISO()} value={form.deposit_date} onChange={set("deposit_date")} /></Field>
        <Field label="Amount deposited (₹)" hint={`Reconciled cash: ${formatINR(reconciled)}`}>
          <input className="input tabular-nums" inputMode="decimal" placeholder={reconciled} value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value.replace(/[^\d.]/g, "") })} />
        </Field>
        {mismatch && <Field label="Reason for mismatch (required)"><input className="input" value={form.mismatch_reason} onChange={set("mismatch_reason")} /></Field>}
      </div>
      {mismatch && diff && <Alert kind="warning">Deposit differs from reconciled cash by {formatINR(diff)} — a bank-mismatch discrepancy will be raised.</Alert>}
      {m.isError && <Alert>{errorText(m.error)}</Alert>}
    </Modal>
  );
}

function SettleModal({ d, onClose }: { d: Deposit; onClose: () => void }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<"settle" | "fail">("settle");
  const [form, setForm] = useState({ settled_amount: d.amount, settled_on: todayISO(), settlement_reference: "", note: "" });
  const diff = isValidAmount(form.settled_amount) ? subtract(d.amount, form.settled_amount) : null;
  const mismatch = diff !== null && compare(diff, "0") !== 0;
  const done = () => { qc.invalidateQueries(); onClose(); };
  const settle = useMutation({ mutationFn: () => api.post(`/deposits/${d.id}/settle/`, form), onSuccess: done });
  const fail = useMutation({ mutationFn: () => api.post(`/deposits/${d.id}/fail/`, { reason: form.note }), onSuccess: done });
  const error = settle.error ?? fail.error;

  return (
    <Modal open onClose={onClose} title={`Reconcile ${d.deposit_number}`} footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      {mode === "settle" ? (
        <Button variant="success" loading={settle.isPending} disabled={!isValidAmount(form.settled_amount) || !form.settlement_reference || (mismatch && !form.note.trim())} onClick={() => settle.mutate()}>Confirm settlement</Button>
      ) : (
        <Button variant="danger" loading={fail.isPending} disabled={!form.note.trim()} onClick={() => fail.mutate()}>Mark failed</Button>
      )}
    </>}>
      <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3 text-sm">
        <div><p className="text-slate-500">Bank / reference</p><p className="font-medium">{d.bank_name} · <span className="font-mono">{d.reference_number}</span></p></div>
        <div className="text-right"><p className="text-slate-500">Deposited</p><p className="font-semibold tabular-nums">{formatINR(d.amount)} on {formatDate(d.deposit_date)}</p></div>
      </div>
      <div className="flex gap-2 text-sm">
        <button onClick={() => setMode("settle")} className={`rounded-full px-3 py-1 ${mode === "settle" ? "bg-emerald-100 text-emerald-800" : "text-slate-500"}`}>Credited in bank statement</button>
        <button onClick={() => setMode("fail")} className={`rounded-full px-3 py-1 ${mode === "fail" ? "bg-rose-100 text-rose-800" : "text-slate-500"}`}>Failed / returned</button>
      </div>
      {mode === "settle" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Amount credited (₹)"><input className="input tabular-nums" inputMode="decimal" value={form.settled_amount} onChange={(e) => setForm({ ...form, settled_amount: e.target.value.replace(/[^\d.]/g, "") })} /></Field>
          <Field label="Credited on"><input type="date" className="input" min={d.deposit_date} max={todayISO()} value={form.settled_on} onChange={(e) => setForm({ ...form, settled_on: e.target.value })} /></Field>
          <Field label="Statement reference" className="sm:col-span-2"><input className="input font-mono" value={form.settlement_reference} onChange={(e) => setForm({ ...form, settlement_reference: e.target.value })} /></Field>
          {mismatch && diff && <div className="sm:col-span-2 space-y-3">
            <Alert kind="warning">Bank credited {formatINR(diff.replace("-", ""))} {compare(diff, "0") > 0 ? "less" : "more"} than deposited — a settlement-mismatch discrepancy will be raised.</Alert>
            <Field label="Reason (required)"><input className="input" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
          </div>}
        </div>
      ) : (
        <Field label="Failure reason (required)" hint="The cash returns to the branch's 'awaiting deposit' pool so it can be re-deposited.">
          <textarea className="input" rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </Field>
      )}
      {error && <Alert>{errorText(error)}</Alert>}
    </Modal>
  );
}
