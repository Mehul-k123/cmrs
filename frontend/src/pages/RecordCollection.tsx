import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Search } from "lucide-react";
import { Fragment, useMemo, useState } from "react";

import { api, errorOf } from "../api/client";
import type { ApiError, Collection, Loan } from "../api/types";
import { Alert, Amount, Button, Card, Field, Modal, PageHeader, Pagination, Spinner, Table } from "../components/ui";
import { formatDate, formatDateTime, formatINR } from "../lib/format";
import { useList } from "../lib/hooks";
import { compare, isValidAmount } from "../lib/money";
import { uuid } from "../lib/uuid";

export default function RecordCollection() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Loan | null>(null);
  const { data, isLoading } = useList<Loan>("/loans/", { status: "ACTIVE", search, page });

  return (
    <div>
      <PageHeader title="Record a collection" subtitle="Choose the customer's loan to record a cash repayment. Partial payments are allowed." />
      <Card padded={false}>
        <div className="border-b border-slate-100 p-3">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input className="input pl-9" placeholder="Search customer or loan number" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
        </div>
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={
            <tr><th className="th">Customer</th><th className="th">Loan</th><th className="th">Next due</th><th className="th num">Outstanding</th><th className="th" /></tr>
          }>
            {data?.results.map((l) => (
              <tr key={l.id} className="hover:bg-slate-50">
                <td className="td font-medium">{l.customer_name}<div className="text-xs text-slate-400">{l.customer_code}</div></td>
                <td className="td">{l.loan_number}</td>
                <td className="td">{formatDate(l.next_due_date)}</td>
                <td className="td num font-semibold"><Amount value={l.outstanding} /></td>
                <td className="td text-right"><Button onClick={() => setSelected(l)}>Collect</Button></td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
      {selected && <CollectModal loan={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

export function CollectModal({ loan, onClose }: { loan: Loan; onClose: () => void }) {
  const qc = useQueryClient();
  // One idempotency key per form instance: retries / double-clicks can never create two receipts.
  const key = useMemo(() => uuid(), []);
  const [amount, setAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [duplicate, setDuplicate] = useState<ApiError | null>(null);
  const [receipt, setReceipt] = useState<Collection | null>(null);

  const m = useMutation({
    mutationFn: async (confirm: boolean) =>
      (await api.post<Collection>("/collections/", { loan: loan.id, amount, notes, confirm_duplicate: confirm }, { headers: { "Idempotency-Key": key } })).data,
    onSuccess: (c) => {
      setReceipt(c);
      qc.invalidateQueries();
    },
    onError: (err) => {
      const e = errorOf(err);
      if (e.code === "possible_duplicate") setDuplicate(e);
    },
  });

  const valid = isValidAmount(amount) && compare(amount, "0") > 0;
  const over = valid && compare(amount, loan.outstanding) > 0;
  const partial = valid && !over && loan.next_due_date;
  const err = m.isError ? errorOf(m.error) : null;

  if (receipt) {
    return (
      <Modal open onClose={onClose} title="Payment recorded" footer={<Button onClick={onClose}>Done</Button>}>
        <div className="text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" />
          <p className="mt-2 text-2xl font-semibold tabular-nums">{formatINR(receipt.amount)}</p>
          <p className="text-sm text-slate-500">received from {receipt.customer_name}</p>
        </div>
        <dl className="grid grid-cols-2 gap-y-2 rounded-lg bg-slate-50 p-4 text-sm">
          <dt className="text-slate-500">Receipt no.</dt><dd className="text-right font-mono font-semibold">{receipt.receipt_number}</dd>
          <dt className="text-slate-500">Loan</dt><dd className="text-right">{receipt.loan_number}</dd>
          <dt className="text-slate-500">Date</dt><dd className="text-right">{formatDateTime(receipt.collected_at)}</dd>
          {receipt.allocations?.map((a) => (
            <Fragment key={a.installment_number}>
              <dt className="text-slate-500">EMI #{a.installment_number} ({formatDate(a.due_date)})</dt>
              <dd className="text-right"><Amount value={a.amount} /></dd>
            </Fragment>
          ))}
        </dl>
        <p className="text-center text-xs text-slate-500">Share the receipt number with the customer as proof of payment.</p>
      </Modal>
    );
  }

  return (
    <Modal open onClose={onClose} title={`Collect from ${loan.customer_name}`} footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      {duplicate ? (
        <Button variant="danger" loading={m.isPending} onClick={() => m.mutate(true)}>Yes, record second payment</Button>
      ) : (
        <Button loading={m.isPending} disabled={!valid || over} onClick={() => m.mutate(false)}>Record payment</Button>
      )}
    </>}>
      <div className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-3 text-sm">
        <div><p className="text-slate-500">Loan</p><p className="font-medium">{loan.loan_number}</p></div>
        <div className="text-right"><p className="text-slate-500">Outstanding</p><p className="font-semibold tabular-nums">{formatINR(loan.outstanding)}</p></div>
      </div>
      {duplicate && <Alert kind="warning">{duplicate.message}</Alert>}
      {err && err.code !== "possible_duplicate" && <Alert>{err.message}</Alert>}
      <Field label="Amount received (₹)" hint={over ? <span className="text-rose-600">Exceeds outstanding — over-collection is not allowed.</span> : partial ? "Applied to the oldest unpaid EMI first." : undefined}>
        <input className="input text-lg tabular-nums" inputMode="decimal" autoFocus placeholder="0.00" value={amount}
          onChange={(e) => { setAmount(e.target.value.replace(/[^\d.]/g, "")); setDuplicate(null); }} />
      </Field>
      <Field label="Notes (optional)"><input className="input" maxLength={255} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
    </Modal>
  );
}
