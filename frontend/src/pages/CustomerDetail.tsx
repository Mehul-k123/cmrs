import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, errorText } from "../api/client";
import type { Customer, Loan } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, Amount, Button, Card, Field, Modal, PageHeader, Spinner, StatusBadge, Table } from "../components/ui";
import { formatDate, todayISO } from "../lib/format";
import { useList, useOne } from "../lib/hooks";
import { isValidAmount } from "../lib/money";

export default function CustomerDetail() {
  const { id } = useParams();
  const { hasRole } = useAuth();
  const customer = useOne<Customer>(`/customers/${id}/`);
  const loans = useList<Loan>("/loans/", { customer: id });
  const [creating, setCreating] = useState(false);

  if (customer.isLoading) return <Spinner />;
  const c = customer.data;
  if (!c) return <Alert>Customer not found or not accessible.</Alert>;

  return (
    <div>
      <PageHeader
        title={c.name}
        subtitle={`${c.customer_code} · ${c.phone} · ${c.branch_name} · Agent: ${c.assigned_agent_name ?? "unassigned"}`}
        actions={hasRole("ADMIN", "BRANCH_MANAGER") && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New loan</Button>}
      />
      <Card title="Loans" padded={false}>
        <Table empty={!loans.data?.results.length} head={
          <tr>
            <th className="th">Loan</th>
            <th className="th">Disbursed</th>
            <th className="th num">Principal</th>
            <th className="th num">Total due</th>
            <th className="th num">Paid</th>
            <th className="th num">Outstanding</th>
            <th className="th">Next due</th>
            <th className="th">Status</th>
          </tr>
        }>
          {loans.data?.results.map((l) => (
            <tr key={l.id} className="hover:bg-slate-50">
              <td className="td"><Link className="font-medium text-brand-700 hover:underline" to={`/loans/${l.id}`}>{l.loan_number}</Link></td>
              <td className="td">{formatDate(l.disbursed_on)}</td>
              <td className="td num"><Amount value={l.principal} /></td>
              <td className="td num"><Amount value={l.total_due} /></td>
              <td className="td num"><Amount value={l.total_paid} /></td>
              <td className="td num font-semibold"><Amount value={l.outstanding} /></td>
              <td className="td">{formatDate(l.next_due_date)}</td>
              <td className="td"><StatusBadge status={l.status} /></td>
            </tr>
          ))}
        </Table>
      </Card>
      {creating && <LoanForm customerId={c.id} onClose={() => setCreating(false)} />}
    </div>
  );
}

function LoanForm({ customerId, onClose }: { customerId: number; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ principal: "", interest_rate: "18", tenure_months: "12", disbursed_on: todayISO() });
  const m = useMutation({
    mutationFn: () => api.post("/loans/", { ...form, customer: customerId, tenure_months: Number(form.tenure_months) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["/loans/"] }); onClose(); },
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });
  const valid = isValidAmount(form.principal) && Number(form.tenure_months) > 0;
  return (
    <Modal open onClose={onClose} title="New loan" footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button loading={m.isPending} disabled={!valid} onClick={() => m.mutate()}>Create loan & schedule</Button>
    </>}>
      {m.isError && <Alert>{errorText(m.error)}</Alert>}
      <Field label="Principal (₹)"><input className="input" inputMode="decimal" value={form.principal} onChange={set("principal")} /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Flat interest % p.a."><input className="input" inputMode="decimal" value={form.interest_rate} onChange={set("interest_rate")} /></Field>
        <Field label="Tenure (months)"><input className="input" type="number" min={1} max={120} value={form.tenure_months} onChange={set("tenure_months")} /></Field>
      </div>
      <Field label="Disbursed on" hint="First EMI falls due one month after disbursal.">
        <input className="input" type="date" value={form.disbursed_on} max={todayISO()} onChange={set("disbursed_on")} />
      </Field>
    </Modal>
  );
}
