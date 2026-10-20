import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Banknote, Clock, Landmark, ShieldCheck, Target, Wallet } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../api/client";
import type { DashboardSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { COLLECTION_STATUSES, Filters, type FilterValues } from "../components/Filters";
import { Amount, Card, Empty, PageHeader, Spinner, Stat, Table } from "../components/ui";
import { daysAgoISO, formatDate, formatINR, titleCase, todayISO } from "../lib/format";
import { clean } from "../lib/hooks";

// Categorical slots 1 & 3 of the validated reference palette (blue / aqua).
const CASH = "#2a78d6";
const DIGITAL = "#1baf7a";
const STAGES: [keyof DashboardSummary["lifecycle"], string][] = [
  ["COLLECTED", "With agents"],
  ["SUBMITTED", "Pending verification"],
  ["BRANCH_RECEIVED", "At branch"],
  ["DEPOSITED", "In bank (unsettled)"],
  ["SETTLED", "Settled"],
];

const compact = (v: number) =>
  v >= 1e5 ? `₹${(v / 1e5).toFixed(1)}L` : v >= 1e3 ? `₹${(v / 1e3).toFixed(0)}k` : `₹${v}`;

export default function Dashboard() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<FilterValues>({ date_from: daysAgoISO(29), date_to: todayISO() });
  const params = clean({ ...filters });
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard", params],
    queryFn: async () => (await api.get<DashboardSummary>("/dashboard/summary/", { params })).data,
    placeholderData: (p) => p,
  });

  const k = data?.kpis ?? {};
  const s = (key: string) => (k[key] as string | undefined) ?? "0";
  const lifecycleMax = data ? Math.max(1, ...STAGES.map(([st]) => Number(data.lifecycle[st]))) : 1;
  const trend = data?.trend.map((t) => ({ date: formatDate(t.date).slice(0, 6), Cash: Number(t.cash), Digital: Number(t.digital) })) ?? [];

  return (
    <div>
      <PageHeader
        title={user?.role === "AGENT" ? "My collections overview" : "Collections dashboard"}
        subtitle={data ? `${formatDate(data.filters.date_from)} – ${formatDate(data.filters.date_to)}${user?.branch_name ? ` · ${user.branch_name}` : ""}` : undefined}
      />
      <Filters value={filters} onChange={(v) => setFilters(v.date_from || v.date_to ? v : { ...v, date_from: daysAgoISO(29), date_to: todayISO() })} statuses={COLLECTION_STATUSES} />

      {isLoading && <Spinner />}
      {isError && <Empty>Could not load the dashboard.</Empty>}
      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Expected (due)" value={formatINR(s("expected_collections"))} icon={<Target className="h-4 w-4" />}
              sub={k.collection_efficiency_pct ? `${k.collection_efficiency_pct}% collection efficiency` : "No dues in period"} />
            <Stat label="Total collected" value={formatINR(s("total_collected"))} icon={<Banknote className="h-4 w-4" />}
              sub={`Cash ${formatINR(s("collected_cash"))} · UPI ${formatINR(s("collected_digital"))}`} />
            <Stat label="Cash held by agents" value={formatINR(s("cash_with_agents"))} tone={Number(s("cash_with_agents")) > 0 ? "warn" : "default"}
              icon={<Wallet className="h-4 w-4" />} sub={`${formatINR(s("cash_pending_verification"))} awaiting branch verification`} />
            <Stat label="Received at branches" value={formatINR(s("received_at_branches"))} icon={<ShieldCheck className="h-4 w-4" />}
              sub={`${formatINR(s("awaiting_bank_deposit"))} not yet deposited`} />
            <Stat label="Bank deposits" value={formatINR(s("bank_deposited"))} icon={<Landmark className="h-4 w-4" />}
              sub={`${formatINR(s("pending_settlement"))} awaiting settlement`} />
            <Stat label="Settled" value={formatINR(s("settled_amount"))} tone="good" icon={<ShieldCheck className="h-4 w-4" />}
              sub={`Cash ${formatINR(s("settled_cash"))} · UPI ${formatINR(s("settled_digital"))}`} />
            <Stat label="Loan outstanding" value={formatINR(s("outstanding_amount"))} icon={<Clock className="h-4 w-4" />}
              sub={`${formatINR(s("overdue_amount"))} overdue`} />
            <Stat label="Open discrepancies" value={String(k.open_discrepancies ?? 0)} tone={Number(k.open_discrepancies) ? "bad" : "good"}
              icon={<AlertTriangle className="h-4 w-4" />}
              sub={`${formatINR(s("open_discrepancy_amount"))} · ${k.failed_deposits ?? 0} failed · ${k.delayed_settlements ?? 0} delayed`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            <Card title="Daily collections" className="lg:col-span-3">
              {trend.length ? (
                <div className="h-64">
                  <ResponsiveContainer>
                    <BarChart data={trend} barCategoryGap="25%">
                      <CartesianGrid vertical={false} stroke="#eef0f3" />
                      <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24} tick={{ fontSize: 11, fill: "#64748b" }} />
                      <YAxis tickFormatter={compact} tickLine={false} axisLine={false} width={52} tick={{ fontSize: 11, fill: "#64748b" }} />
                      <Tooltip formatter={(v: number) => formatINR(v)} cursor={{ fill: "#f1f5f9" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 12, color: "#475569" }} />
                      <Bar dataKey="Cash" stackId="a" fill={CASH} stroke="#fff" strokeWidth={2} />
                      <Bar dataKey="Digital" stackId="a" fill={DIGITAL} stroke="#fff" strokeWidth={2} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Empty>No collections in this period.</Empty>
              )}
            </Card>

            <Card title="Where the money is (collection lifecycle)" className="lg:col-span-2">
              <ul className="space-y-3">
                {STAGES.map(([st, label]) => {
                  const v = data.lifecycle[st];
                  return (
                    <li key={st} title={`${label}: ${formatINR(v)}`}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span className="text-slate-600">{label}</span>
                        <span className="font-medium tabular-nums text-slate-800">{formatINR(v)}</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-100">
                        <div className="h-2 rounded-full" style={{ width: `${(Number(v) / lifecycleMax) * 100}%`, background: CASH }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
              <p className="mt-4 text-xs text-slate-500">Expected → Collected → Branch received → Bank deposited → Settled</p>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            {user?.role !== "AGENT" && (
              <Card title="By agent" padded={false}>
                <Table
                  empty={!data.by_agent.length}
                  head={
                    <tr>
                      <th className="th">Agent</th>
                      <th className="th num">Collected</th>
                      <th className="th num">In hand</th>
                      <th className="th num">Pending</th>
                      <th className="th num">Shortages</th>
                    </tr>
                  }
                >
                  {data.by_agent.map((a) => (
                    <tr key={a.agent_id}>
                      <td className="td font-medium">{a.agent}<span className="ml-1 text-xs text-slate-400">({a.count})</span></td>
                      <td className="td num"><Amount value={a.collected} /></td>
                      <td className="td num"><Amount value={a.cash_in_hand} /></td>
                      <td className="td num"><Amount value={a.pending_verification} /></td>
                      <td className="td num">{Number(a.shortages) ? <Amount value={a.shortages} className="text-rose-600" /> : "—"}</td>
                    </tr>
                  ))}
                </Table>
              </Card>
            )}
            {(user?.role === "ADMIN" || user?.role === "FINANCE") && (
              <Card title="By branch" padded={false}>
                <Table
                  empty={!data.by_branch.length}
                  head={
                    <tr>
                      <th className="th">Branch</th>
                      <th className="th num">Collections</th>
                      <th className="th num">Collected</th>
                      <th className="th num">With agents</th>
                    </tr>
                  }
                >
                  {data.by_branch.map((b) => (
                    <tr key={b.branch_id}>
                      <td className="td font-medium">{b.branch}</td>
                      <td className="td num">{b.count}</td>
                      <td className="td num"><Amount value={b.collected} /></td>
                      <td className="td num"><Amount value={b.cash_with_agents} /></td>
                    </tr>
                  ))}
                </Table>
              </Card>
            )}
            {user?.role !== "AGENT" && (
              <Card title="Open reconciliation discrepancies" padded={false}>
                <Table
                  empty={!data.discrepancies_by_type.length}
                  head={
                    <tr>
                      <th className="th">Type</th>
                      <th className="th num">Count</th>
                      <th className="th num">Amount</th>
                    </tr>
                  }
                >
                  {data.discrepancies_by_type.map((d) => (
                    <tr key={d.type}>
                      <td className="td">{titleCase(d.type)}</td>
                      <td className="td num">{d.count}</td>
                      <td className="td num"><Amount value={d.amount} /></td>
                    </tr>
                  ))}
                </Table>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
