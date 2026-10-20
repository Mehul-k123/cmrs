import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Lock, Undo2 } from "lucide-react";
import { useState } from "react";

import { api, errorText } from "../api/client";
import type { Collection } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { COLLECTION_STATUSES, Filters, type FilterValues } from "../components/Filters";
import { Alert, Amount, Button, Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { useList } from "../lib/hooks";

export default function CollectionsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<FilterValues>({});
  const [mode, setMode] = useState("");
  const [page, setPage] = useState(1);
  const [reversing, setReversing] = useState<Collection | null>(null);
  const { data, isLoading } = useList<Collection>("/collections/", { ...filters, mode, page });

  const canReverse = (c: Collection) =>
    c.status !== "REVERSED" && c.status !== "SUBMITTED" && (user?.role === "ADMIN" || (user?.role === "BRANCH_MANAGER" && !c.is_locked));

  return (
    <div>
      <PageHeader title="Collections" subtitle="Every repayment received, with its position in the cash lifecycle. Reconciled entries are locked." />
      <Filters value={filters} onChange={(v) => { setFilters(v); setPage(1); }} statuses={COLLECTION_STATUSES}>
        <label className="w-32">
          <span className="label">Mode</span>
          <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="">All</option><option value="CASH">Cash</option><option value="UPI">UPI</option>
          </select>
        </label>
      </Filters>
      <Card padded={false}>
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={
            <tr><th className="th">Receipt</th><th className="th">Collected</th><th className="th">Customer / Loan</th><th className="th">Agent</th><th className="th">Branch</th><th className="th num">Amount</th><th className="th">Status</th><th className="th" /></tr>
          }>
            {data?.results.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="td font-mono text-xs">
                  <span className="inline-flex items-center gap-1">{c.is_locked && <Lock className="h-3 w-3 text-slate-400" aria-label="Locked" />}{c.receipt_number}</span>
                </td>
                <td className="td">{formatDateTime(c.collected_at)}</td>
                <td className="td">{c.customer_name}<div className="text-xs text-slate-400">{c.loan_number}</div></td>
                <td className="td">{c.agent_name ?? <span className="text-slate-400">UPI gateway</span>}</td>
                <td className="td">{c.branch_name}</td>
                <td className="td num"><Amount value={c.amount} className={c.status === "REVERSED" ? "line-through text-slate-400" : ""} /></td>
                <td className="td"><StatusBadge status={c.status} /></td>
                <td className="td text-right">
                  {canReverse(c) && <Button variant="ghost" onClick={() => setReversing(c)}><Undo2 className="h-4 w-4" /> Reverse</Button>}
                </td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
      {reversing && <ReverseModal c={reversing} onClose={() => setReversing(null)} />}
    </div>
  );
}

function ReverseModal({ c, onClose }: { c: Collection; onClose: () => void }) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const m = useMutation({
    mutationFn: () => api.post(`/collections/${c.id}/reverse/`, { reason }),
    onSuccess: () => { qc.invalidateQueries(); onClose(); },
  });
  return (
    <Modal open onClose={onClose} title={`Reverse ${c.receipt_number}`} footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button variant="danger" loading={m.isPending} disabled={!reason.trim()} onClick={() => m.mutate()}>Reverse collection</Button>
    </>}>
      <Alert kind="warning">
        The loan balance will be restored. {c.is_locked && "This collection is already reconciled — an adjustment discrepancy will be opened for finance."}
      </Alert>
      {m.isError && <Alert>{errorText(m.error)}</Alert>}
      <Field label="Reason (required, audit-logged)"><textarea className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
    </Modal>
  );
}
