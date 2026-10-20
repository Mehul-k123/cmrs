import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, errorText } from "../api/client";
import type { Discrepancy } from "../api/types";
import { Filters, type FilterValues } from "../components/Filters";
import { Alert, Amount, Button, Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table } from "../components/ui";
import { formatDateTime, titleCase } from "../lib/format";
import { useList } from "../lib/hooks";

const TYPES = ["SHORTAGE", "EXCESS", "BANK_MISMATCH", "SETTLEMENT_MISMATCH", "REVERSAL_ADJUSTMENT"];

export default function DiscrepanciesPage() {
  const [filters, setFilters] = useState<FilterValues>({ status: "OPEN" });
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [resolving, setResolving] = useState<Discrepancy | null>(null);
  const { data, isLoading } = useList<Discrepancy>("/discrepancies/", { ...filters, type, page });

  return (
    <div>
      <PageHeader title="Reconciliation discrepancies" subtitle="Differences between expected, branch-counted, deposited and bank-settled amounts. Positive = shortfall." />
      <Filters value={filters} onChange={(v) => { setFilters(v); setPage(1); }} statuses={[["OPEN", "Open"], ["RESOLVED", "Resolved"]]}>
        <label className="w-48">
          <span className="label">Type</span>
          <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">All types</option>
            {TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
          </select>
        </label>
      </Filters>
      <Card padded={false}>
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={
            <tr><th className="th">Type</th><th className="th">Raised</th><th className="th">Reference</th><th className="th">Branch / Agent</th><th className="th num">Expected</th><th className="th num">Actual</th><th className="th num">Difference</th><th className="th">Reason</th><th className="th">Status</th><th className="th" /></tr>
          }>
            {data?.results.map((d) => (
              <tr key={d.id} className="align-top hover:bg-slate-50">
                <td className="td font-medium">{titleCase(d.type)}</td>
                <td className="td">{formatDateTime(d.created_at)}<div className="text-xs text-slate-400">by {d.raised_by_name}</div></td>
                <td className="td font-mono text-xs">{d.submission_number ?? d.deposit_number ?? d.receipt_number}</td>
                <td className="td">{d.branch_name}<div className="text-xs text-slate-400">{d.agent_name ?? "—"}</div></td>
                <td className="td num"><Amount value={d.expected_amount} /></td>
                <td className="td num"><Amount value={d.actual_amount} /></td>
                <td className="td num font-semibold"><Amount value={d.difference} signed /></td>
                <td className="td max-w-xs whitespace-normal text-slate-600">{d.reason}
                  {d.resolution_note && <div className="mt-1 text-xs text-emerald-700">✓ {d.resolution_note} — {d.resolved_by_name}</div>}</td>
                <td className="td"><StatusBadge status={d.status} /></td>
                <td className="td text-right">{d.status === "OPEN" && <Button variant="secondary" onClick={() => setResolving(d)}>Resolve</Button>}</td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
      {resolving && <ResolveModal d={resolving} onClose={() => setResolving(null)} />}
    </div>
  );
}

function ResolveModal({ d, onClose }: { d: Discrepancy; onClose: () => void }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const m = useMutation({ mutationFn: () => api.post(`/discrepancies/${d.id}/resolve/`, { note }), onSuccess: () => { qc.invalidateQueries(); onClose(); } });
  return (
    <Modal open onClose={onClose} title={`Resolve ${titleCase(d.type)}`} footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button loading={m.isPending} disabled={!note.trim()} onClick={() => m.mutate()}>Mark resolved</Button>
    </>}>
      <p className="text-sm text-slate-600">Difference <Amount value={d.difference} signed /> — {d.reason}</p>
      {m.isError && <Alert>{errorText(m.error)}</Alert>}
      <Field label="Resolution (e.g. recovered from agent, written off, bank credited later)">
        <textarea className="input" rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
    </Modal>
  );
}
