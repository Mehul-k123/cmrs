import { useState } from "react";

import type { AuditEntry } from "../api/types";
import { Card, PageHeader, Pagination, Spinner, Table } from "../components/ui";
import { formatDateTime } from "../lib/format";
import { useList } from "../lib/hooks";

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [entity, setEntity] = useState("");
  const { data, isLoading } = useList<AuditEntry>("/audit-logs/", { page, entity_type: entity });

  return (
    <div>
      <PageHeader title="Audit log" subtitle="Immutable record of every financial state change: who, what, when, from where." />
      <Card padded={false} title="Events" actions={
        <select className="input w-48" value={entity} onChange={(e) => { setEntity(e.target.value); setPage(1); }}>
          <option value="">All entities</option>
          {["Collection", "CashSubmission", "BankDeposit", "Discrepancy", "Loan", "PaymentIntent"].map((e) => <option key={e}>{e}</option>)}
        </select>}>
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={<tr><th className="th">When</th><th className="th">Actor</th><th className="th">Action</th><th className="th">Entity</th><th className="th">Change</th><th className="th">IP</th></tr>}>
            {data?.results.map((a) => (
              <tr key={a.id} className="align-top">
                <td className="td">{formatDateTime(a.created_at)}</td>
                <td className="td">{a.actor_name ?? <span className="text-slate-400">system</span>}</td>
                <td className="td font-mono text-xs">{a.action}</td>
                <td className="td">{a.entity_type} #{a.entity_id}</td>
                <td className="td max-w-md whitespace-normal font-mono text-[11px] text-slate-500">
                  {a.before && <div className="text-rose-600">− {JSON.stringify(a.before)}</div>}
                  {a.after && <div className="text-emerald-700">+ {JSON.stringify(a.after)}</div>}
                </td>
                <td className="td text-xs text-slate-400">{a.ip_address ?? "—"}</td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
    </div>
  );
}
