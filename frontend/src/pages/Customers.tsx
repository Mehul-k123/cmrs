import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, errorText } from "../api/client";
import type { Customer } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, Button, Card, Field, Modal, PageHeader, Pagination, Spinner, Table } from "../components/ui";
import { useAgents, useBranches, useList } from "../lib/hooks";

export default function CustomersPage() {
  const { user, hasRole } = useAuth();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useList<Customer>("/customers/", { search, page });

  return (
    <div>
      <PageHeader
        title={user?.role === "AGENT" ? "My customers" : "Customers"}
        subtitle="Customers, their loans, repayment schedules and outstanding balances."
        actions={hasRole("ADMIN", "BRANCH_MANAGER") && (
          <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New customer</Button>
        )}
      />
      <Card padded={false}>
        <div className="border-b border-slate-100 p-3">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input className="input pl-9" placeholder="Search name, code or phone" value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
        </div>
        {isLoading ? <Spinner /> : (
          <Table empty={!data?.results.length} head={
            <tr>
              <th className="th">Customer</th>
              <th className="th">Phone</th>
              <th className="th">Branch</th>
              <th className="th">Agent</th>
              <th className="th num">Active loans</th>
            </tr>
          }>
            {data?.results.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="td">
                  <Link to={`/customers/${c.id}`} className="font-medium text-brand-700 hover:underline">{c.name}</Link>
                  <div className="text-xs text-slate-400">{c.customer_code}</div>
                </td>
                <td className="td">{c.phone}</td>
                <td className="td">{c.branch_name}</td>
                <td className="td">{c.assigned_agent_name ?? <span className="text-slate-400">Unassigned</span>}</td>
                <td className="td num">{c.active_loans}</td>
              </tr>
            ))}
          </Table>
        )}
        <Pagination page={page} count={data?.count ?? 0} onChange={setPage} />
      </Card>
      {creating && <CustomerForm onClose={() => setCreating(false)} />}
    </div>
  );
}

function CustomerForm({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const isAdmin = user?.role === "ADMIN";
  const branches = useBranches(isAdmin);
  const [form, setForm] = useState({ name: "", phone: "", address: "", branch: String(user?.branch ?? ""), assigned_agent: "" });
  const agents = useAgents(form.branch || undefined, Boolean(form.branch));
  const m = useMutation({
    mutationFn: () => api.post("/customers/", { ...form, branch: Number(form.branch), assigned_agent: form.assigned_agent ? Number(form.assigned_agent) : null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["/customers/"] }); onClose(); },
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  return (
    <Modal open onClose={onClose} title="New customer" footer={<>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button loading={m.isPending} disabled={!form.name || !form.phone || !form.branch} onClick={() => m.mutate()}>Create</Button>
    </>}>
      {m.isError && <Alert>{errorText(m.error)}</Alert>}
      <Field label="Full name"><input className="input" value={form.name} onChange={set("name")} /></Field>
      <Field label="Phone"><input className="input" value={form.phone} onChange={set("phone")} inputMode="tel" maxLength={15} /></Field>
      <Field label="Address"><textarea className="input" rows={2} value={form.address} onChange={set("address")} /></Field>
      {isAdmin && (
        <Field label="Branch">
          <select className="input" value={form.branch} onChange={set("branch")}>
            <option value="">Select…</option>
            {branches.data?.results.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
        </Field>
      )}
      <Field label="Assigned collection agent">
        <select className="input" value={form.assigned_agent} onChange={set("assigned_agent")}>
          <option value="">Unassigned</option>
          {agents.data?.results.map((a) => <option key={a.id} value={a.id}>{a.display_name}</option>)}
        </select>
      </Field>
    </Modal>
  );
}
