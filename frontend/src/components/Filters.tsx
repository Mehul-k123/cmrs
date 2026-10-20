import type { ReactNode } from "react";

import { useAuth } from "../auth/AuthContext";
import { useAgents, useBranches } from "../lib/hooks";

export interface FilterValues {
  date_from?: string;
  date_to?: string;
  branch?: string;
  agent?: string;
  status?: string;
}

/** One row of filters above a list or dashboard. Branch/agent pickers only render for roles that can use them. */
export function Filters({ value, onChange, statuses, showAgent = true, children }: {
  value: FilterValues;
  onChange: (v: FilterValues) => void;
  statuses?: [string, string][];
  showAgent?: boolean;
  children?: ReactNode;
}) {
  const { user } = useAuth();
  const orgWide = user?.role === "ADMIN" || user?.role === "FINANCE";
  const canPickAgent = showAgent && user?.role !== "AGENT";
  const branches = useBranches(orgWide);
  const agents = useAgents(orgWide ? value.branch : user?.branch, canPickAgent);
  const set = (k: keyof FilterValues, v: string) => onChange({ ...value, [k]: v || undefined, ...(k === "branch" ? { agent: undefined } : {}) });

  return (
    <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <label className="w-[9.5rem]">
        <span className="label">From</span>
        <input type="date" className="input" value={value.date_from ?? ""} onChange={(e) => set("date_from", e.target.value)} />
      </label>
      <label className="w-[9.5rem]">
        <span className="label">To</span>
        <input type="date" className="input" value={value.date_to ?? ""} onChange={(e) => set("date_to", e.target.value)} />
      </label>
      {orgWide && (
        <label className="w-44">
          <span className="label">Branch</span>
          <select className="input" value={value.branch ?? ""} onChange={(e) => set("branch", e.target.value)}>
            <option value="">All branches</option>
            {branches.data?.results.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>
        </label>
      )}
      {canPickAgent && (
        <label className="w-44">
          <span className="label">Agent</span>
          <select className="input" value={value.agent ?? ""} onChange={(e) => set("agent", e.target.value)}>
            <option value="">All agents</option>
            {agents.data?.results.map((a) => (
              <option key={a.id} value={a.id}>{a.display_name}</option>
            ))}
          </select>
        </label>
      )}
      {statuses && (
        <label className="w-48">
          <span className="label">Status</span>
          <select className="input" value={value.status ?? ""} onChange={(e) => set("status", e.target.value)}>
            <option value="">All statuses</option>
            {statuses.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
      )}
      {children}
      <button className="ml-auto text-xs font-medium text-slate-500 hover:text-brand-700" onClick={() => onChange({})}>
        Reset
      </button>
    </div>
  );
}

export const COLLECTION_STATUSES: [string, string][] = [
  ["COLLECTED", "With agent"],
  ["SUBMITTED", "Pending verification"],
  ["BRANCH_RECEIVED", "At branch"],
  ["DEPOSITED", "Deposited"],
  ["SETTLED", "Settled"],
  ["REVERSED", "Reversed"],
];
