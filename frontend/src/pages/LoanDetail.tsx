import { useQuery } from "@tanstack/react-query";
import { ReceiptIndianRupee, Smartphone } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { Collection, Installment, Loan } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, Amount, Button, Card, PageHeader, Spinner, Stat, StatusBadge, Table } from "../components/ui";
import { formatDate, formatDateTime, formatINR } from "../lib/format";
import { useOne } from "../lib/hooks";
import { CollectModal } from "./RecordCollection";
import { PayOnlineModal } from "./Payments";

export default function LoanDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const loan = useOne<Loan>(`/loans/${id}/`);
  const schedule = useQuery({ queryKey: [`/loans/${id}/`, "schedule"], queryFn: async () => (await api.get<Installment[]>(`/loans/${id}/schedule/`)).data });
  const history = useQuery({ queryKey: [`/loans/${id}/`, "repayments"], queryFn: async () => (await api.get<Collection[]>(`/loans/${id}/repayments/`)).data });
  const [collecting, setCollecting] = useState(false);
  const [paying, setPaying] = useState(false);

  if (loan.isLoading) return <Spinner />;
  const l = loan.data;
  if (!l) return <Alert>Loan not found or not accessible.</Alert>;
  const open = l.status === "ACTIVE" && Number(l.outstanding) > 0;

  return (
    <div>
      <PageHeader
        title={`Loan ${l.loan_number}`}
        subtitle={<><Link className="text-brand-700 hover:underline" to={`/customers/${l.customer}`}>{l.customer_name}</Link> · {l.branch_name} · disbursed {formatDate(l.disbursed_on)} · {l.interest_rate}% flat · {l.tenure_months} months</>}
        actions={open && <>
          {user?.role === "AGENT" && <Button onClick={() => setCollecting(true)}><ReceiptIndianRupee className="h-4 w-4" /> Record cash</Button>}
          <Button variant="secondary" onClick={() => setPaying(true)}><Smartphone className="h-4 w-4" /> UPI payment link</Button>
        </>}
      />
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Principal" value={formatINR(l.principal)} />
        <Stat label="Total repayable" value={formatINR(l.total_due)} />
        <Stat label="Repaid" value={formatINR(l.total_paid)} tone="good" />
        <Stat label="Outstanding" value={formatINR(l.outstanding)} tone={open ? "warn" : "good"} sub={<StatusBadge status={l.status} />} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Repayment schedule" padded={false}>
          {schedule.isLoading ? <Spinner /> : (
            <Table head={<tr><th className="th">#</th><th className="th">Due date</th><th className="th num">Due</th><th className="th num">Paid</th><th className="th num">Balance</th><th className="th">Status</th></tr>}>
              {schedule.data?.map((i) => (
                <tr key={i.id} className={i.is_overdue ? "bg-rose-50/40" : ""}>
                  <td className="td">{i.number}</td>
                  <td className="td">{formatDate(i.due_date)}</td>
                  <td className="td num"><Amount value={i.amount_due} /></td>
                  <td className="td num"><Amount value={i.amount_paid} /></td>
                  <td className="td num"><Amount value={i.balance} /></td>
                  <td className="td"><StatusBadge status={i.is_overdue ? "OPEN" : i.status} label={i.is_overdue ? "Overdue" : undefined} /></td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
        <Card title="Repayment history" padded={false}>
          <Table empty={!history.data?.length} head={<tr><th className="th">Receipt</th><th className="th">When</th><th className="th">Mode</th><th className="th num">Amount</th><th className="th">Status</th></tr>}>
            {history.data?.map((c) => (
              <tr key={c.id}>
                <td className="td font-mono text-xs">{c.receipt_number}<div className="font-sans text-slate-400">{c.agent_name ?? "Gateway"}</div></td>
                <td className="td">{formatDateTime(c.collected_at)}</td>
                <td className="td">{c.mode}</td>
                <td className="td num"><Amount value={c.amount} className={c.status === "REVERSED" ? "line-through text-slate-400" : ""} /></td>
                <td className="td"><StatusBadge status={c.status} /></td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
      {collecting && <CollectModal loan={l} onClose={() => setCollecting(false)} />}
      {paying && <PayOnlineModal loan={l} onClose={() => setPaying(false)} />}
    </div>
  );
}
