import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Smartphone, XCircle } from "lucide-react";
import { useState } from "react";

import { api, errorText } from "../api/client";
import type { Loan, PaymentIntent } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, Amount, Button, Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table } from "../components/ui";
import { formatDateTime, formatINR } from "../lib/format";
import { useList } from "../lib/hooks";
import { compare, isValidAmount } from "../lib/money";

export default function PaymentsPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const { data, isLoading } = useList<PaymentIntent>("/payments/intents/", { page, status });
  const settle = useMutation({ mutationFn: () => api.post("/payments/intents/simulate-settlement/"), onSuccess: () => qc.invalidateQueries() });

  return (
    <div>
      <PageHeader title="UPI / digital payments" subtitle="Repayments through the (mock) payment gateway. They skip agent & branch cash handling and settle directly."
        actions={hasRole("FINANCE", "ADMIN") && <Button variant="secondary" loading={settle.isPending} onClick={() => settle.mutate()}>Simulate gateway settlement</Button>} />
      {settle.data && <div className="mb-4"><Alert kind="success">Gateway settlement processed: {(settle.data.data as { count: number }).count} payment(s) settled.</Alert></div>}
      <Card padded={false} actions={
        <select className="input w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option><option value="CREATED">Awaiting payment</option><option value="PAID">Paid</option><option value="SETTLED">Settled</option><option value="FAILED">Failed</option>
        </select>} title="Payment requests">
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={<tr><th className="th">Request</th><th className="th">Created</th><th className="th">Customer / Loan</th><th className="th num">Amount</th><th className="th">Receipt</th><th className="th">Status</th></tr>}>
            {data?.results.map((p) => (
              <tr key={p.id}>
                <td className="td font-mono text-xs">{p.intent_number}<div className="text-slate-400">{p.gateway_ref}</div></td>
                <td className="td">{formatDateTime(p.created_at)}</td>
                <td className="td">{p.customer_name}<div className="text-xs text-slate-400">{p.loan_number}</div></td>
                <td className="td num"><Amount value={p.amount} /></td>
                <td className="td font-mono text-xs">{p.receipt_number ?? "—"}</td>
                <td className="td"><StatusBadge status={p.status} />{p.failure_reason && <div className="max-w-[14rem] whitespace-normal text-xs text-rose-600">{p.failure_reason}</div>}</td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
    </div>
  );
}

export function PayOnlineModal({ loan, onClose }: { loan: Loan; onClose: () => void }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState("");
  const [intent, setIntent] = useState<PaymentIntent | null>(null);
  const create = useMutation({ mutationFn: async () => (await api.post<PaymentIntent>("/payments/intents/", { loan: loan.id, amount })).data, onSuccess: setIntent });
  const simulate = useMutation({
    mutationFn: async (outcome: "success" | "failure") => (await api.post<PaymentIntent>(`/payments/intents/${intent!.id}/simulate/`, { outcome })).data,
    onSuccess: (p) => { setIntent(p); qc.invalidateQueries(); },
  });
  const valid = isValidAmount(amount) && compare(amount, "0") > 0 && compare(amount, loan.outstanding) <= 0;
  const error = create.error ?? simulate.error;

  return (
    <Modal open onClose={onClose} title="UPI payment request" footer={!intent ? <>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button loading={create.isPending} disabled={!valid} onClick={() => create.mutate()}><Smartphone className="h-4 w-4" /> Generate payment link</Button>
    </> : <Button onClick={onClose}>Close</Button>}>
      {error && <Alert>{errorText(error)}</Alert>}
      {!intent ? (
        <Field label="Amount (₹)" hint={`Outstanding ${formatINR(loan.outstanding)}`}>
          <input className="input tabular-nums" inputMode="decimal" autoFocus value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
      ) : intent.status === "CREATED" ? (
        <div className="space-y-4 text-center">
          <p className="text-sm text-slate-600">Payment link for <b>{formatINR(intent.amount)}</b> sent to {intent.customer_name}.</p>
          <p className="break-all rounded bg-slate-50 p-2 font-mono text-xs text-slate-500">{intent.payment_url ?? intent.gateway_ref}</p>
          <p className="text-xs text-slate-400">Mock gateway — simulate the customer's action:</p>
          <div className="flex justify-center gap-2">
            <Button variant="success" loading={simulate.isPending} onClick={() => simulate.mutate("success")}>Customer pays</Button>
            <Button variant="danger" loading={simulate.isPending} onClick={() => simulate.mutate("failure")}>Payment fails</Button>
          </div>
        </div>
      ) : (
        <div className="text-center">
          {intent.status === "PAID" ? <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-500" /> : <XCircle className="mx-auto h-12 w-12 text-rose-500" />}
          <p className="mt-2 font-semibold">{intent.status === "PAID" ? `Received ${formatINR(intent.amount)}` : "Payment failed"}</p>
          {intent.receipt_number && <p className="font-mono text-sm text-slate-500">Receipt {intent.receipt_number}</p>}
          {intent.failure_reason && <p className="text-sm text-rose-600">{intent.failure_reason}</p>}
        </div>
      )}
    </Modal>
  );
}
