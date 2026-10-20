import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, errorText } from "../api/client";
import type { Submission } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Filters, type FilterValues } from "../components/Filters";
import { Alert, Amount, Button, Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table } from "../components/ui";
import { formatDateTime, formatINR } from "../lib/format";
import { useList, useOne } from "../lib/hooks";
import { compare, isValidAmount, subtract } from "../lib/money";

const STATUSES: [string, string][] = [
  ["SUBMITTED", "Pending verification"],
  ["APPROVED", "Approved"],
  ["REJECTED", "Rejected"],
  ["DEPOSITED", "Deposited"],
  ["SETTLED", "Settled"],
];

export default function SubmissionsPage() {
  const { user } = useAuth();
  const isReviewer = user?.role === "BRANCH_MANAGER" || user?.role === "ADMIN";
  const [filters, setFilters] = useState<FilterValues>(isReviewer ? { status: "SUBMITTED" } : {});
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  const { data, isLoading } = useList<Submission>("/submissions/", { ...filters, page });

  return (
    <div>
      <PageHeader title="Cash submissions" subtitle={isReviewer ? "Count the cash, compare with expected, then approve or reject." : "Cash you have handed over to your branch."} />
      <Filters value={filters} onChange={(v) => { setFilters(v); setPage(1); }} statuses={STATUSES} />
      <Card padded={false}>
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={
            <tr><th className="th">Submission</th><th className="th">Agent</th><th className="th">Submitted</th><th className="th num">Expected</th><th className="th num">Received</th><th className="th num">Difference</th><th className="th">Status</th><th className="th" /></tr>
          }>
            {data?.results.map((s) => (
              <tr key={s.id} className="hover:bg-slate-50">
                <td className="td font-mono text-xs">{s.submission_number}<div className="font-sans text-slate-400">{s.item_count} collections</div></td>
                <td className="td">{s.agent_name}<div className="text-xs text-slate-400">{s.branch_name}</div></td>
                <td className="td">{formatDateTime(s.submitted_at)}</td>
                <td className="td num"><Amount value={s.expected_amount} /></td>
                <td className="td num"><Amount value={s.received_amount} /></td>
                <td className="td num">{s.difference !== null ? <Amount value={s.difference} signed /> : "—"}</td>
                <td className="td"><StatusBadge status={s.status} /></td>
                <td className="td text-right">
                  <Button variant={s.status === "SUBMITTED" && isReviewer ? "primary" : "secondary"} onClick={() => setOpen(s.id)}>
                    {s.status === "SUBMITTED" && isReviewer ? "Verify" : "View"}
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
      {open && <SubmissionModal id={open} canReview={isReviewer} onClose={() => setOpen(null)} />}
    </div>
  );
}

function SubmissionModal({ id, canReview, onClose }: { id: number; canReview: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: s, isLoading } = useOne<Submission>(`/submissions/${id}/`);
  const [received, setReceived] = useState("");
  const [note, setNote] = useState("");
  const [rejecting, setRejecting] = useState(false);

  const done = () => { qc.invalidateQueries(); onClose(); };
  const approve = useMutation({ mutationFn: () => api.post(`/submissions/${id}/approve/`, { received_amount: received, note }), onSuccess: done });
  const reject = useMutation({ mutationFn: () => api.post(`/submissions/${id}/reject/`, { reason: note }), onSuccess: done });

  const pending = s?.status === "SUBMITTED" && canReview;
  const diff = s && isValidAmount(received) ? subtract(s.expected_amount, received) : null;
  const mismatch = diff !== null && compare(diff, "0") !== 0;
  const error = approve.error ?? reject.error;

  return (
    <Modal open wide onClose={onClose} title={s ? `Submission ${s.submission_number}` : "Submission"} footer={pending && s && (
      rejecting ? <>
        <Button variant="secondary" onClick={() => setRejecting(false)}>Back</Button>
        <Button variant="danger" loading={reject.isPending} disabled={!note.trim()} onClick={() => reject.mutate()}>Confirm rejection</Button>
      </> : <>
        <Button variant="secondary" onClick={() => setRejecting(true)}>Reject</Button>
        <Button variant="success" loading={approve.isPending} disabled={!isValidAmount(received) || (mismatch && !note.trim())} onClick={() => approve.mutate()}>
          {mismatch ? "Approve with discrepancy" : "Approve"}
        </Button>
      </>
    )}>
      {isLoading || !s ? <Spinner /> : (
        <>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><p className="text-slate-500">Agent</p><p className="font-medium">{s.agent_name}</p></div>
            <div><p className="text-slate-500">Submitted</p><p>{formatDateTime(s.submitted_at)}</p></div>
            <div><p className="text-slate-500">Declared by agent</p><p className="tabular-nums">{formatINR(s.declared_amount)}</p></div>
            <div><p className="text-slate-500">Status</p><StatusBadge status={s.status} /></div>
          </div>
          {s.agent_note && <Alert kind="info">Agent note: {s.agent_note}</Alert>}
          <div className="max-h-60 overflow-y-auto rounded-lg border border-slate-100">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50"><tr><th className="th">Receipt</th><th className="th">Customer</th><th className="th">Collected</th><th className="th num">Amount</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {s.items?.map((i) => (
                  <tr key={i.collection}><td className="td font-mono text-xs">{i.receipt_number}</td><td className="td">{i.customer_name}</td><td className="td">{formatDateTime(i.collected_at)}</td><td className="td num"><Amount value={i.amount} /></td></tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-3 gap-3 rounded-xl bg-slate-50 p-4 text-center">
            <div><p className="text-xs uppercase tracking-wide text-slate-500">Expected</p><p className="text-lg font-semibold tabular-nums">{formatINR(s.expected_amount)}</p></div>
            <div><p className="text-xs uppercase tracking-wide text-slate-500">Received</p><p className="text-lg font-semibold tabular-nums">{formatINR(pending ? (isValidAmount(received) ? received : null) : s.received_amount)}</p></div>
            <div><p className="text-xs uppercase tracking-wide text-slate-500">Difference</p><p className="text-lg font-semibold"><Amount value={pending ? diff : s.difference} signed /></p></div>
          </div>

          {!pending && s.review_note && <Alert kind={s.status === "REJECTED" ? "error" : "info"}>{s.reviewed_by_name}: {s.review_note}</Alert>}

          {pending && (rejecting ? (
            <Field label="Rejection reason (required)" hint="The cash goes back to the agent, who can recount and resubmit.">
              <textarea className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
            </Field>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Cash counted at branch (₹)">
                <input className="input text-lg tabular-nums" inputMode="decimal" autoFocus placeholder={s.expected_amount} value={received} onChange={(e) => setReceived(e.target.value.replace(/[^\d.]/g, ""))} />
              </Field>
              <Field label={mismatch ? "Reason for discrepancy (required)" : "Note (optional)"}>
                <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
              </Field>
              {mismatch && diff && <div className="sm:col-span-2"><Alert kind="warning">
                {compare(diff, "0") > 0 ? `Shortage of ${formatINR(diff)}` : `Excess of ${formatINR(diff.replace("-", ""))}`} will be recorded as a discrepancy against {s.agent_name}.
              </Alert></div>}
            </div>
          ))}
          {error && <Alert>{errorText(error)}</Alert>}
        </>
      )}
    </Modal>
  );
}
