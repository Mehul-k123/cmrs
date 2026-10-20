import clsx from "clsx";
import { Loader2, X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";

import { titleCase } from "../lib/format";

type Variant = "primary" | "secondary" | "danger" | "ghost" | "success";

export function Button({
  variant = "primary",
  loading,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  const styles: Record<Variant, string> = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
    secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 shadow-sm",
    danger: "bg-rose-600 text-white hover:bg-rose-700 shadow-sm",
    success: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm",
    ghost: "text-slate-600 hover:bg-slate-100",
  };
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className, padded = true }: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={clsx("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className={clsx(padded && "p-5")}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  COLLECTED: "bg-amber-50 text-amber-700 ring-amber-200",
  SUBMITTED: "bg-sky-50 text-sky-700 ring-sky-200",
  BRANCH_RECEIVED: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  APPROVED: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  DEPOSITED: "bg-violet-50 text-violet-700 ring-violet-200",
  SETTLED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  PAID: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  RESOLVED: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  ACTIVE: "bg-sky-50 text-sky-700 ring-sky-200",
  CLOSED: "bg-slate-100 text-slate-600 ring-slate-200",
  REVERSED: "bg-slate-100 text-slate-500 ring-slate-200 line-through",
  REJECTED: "bg-rose-50 text-rose-700 ring-rose-200",
  FAILED: "bg-rose-50 text-rose-700 ring-rose-200",
  OPEN: "bg-rose-50 text-rose-700 ring-rose-200",
  PARTIAL: "bg-amber-50 text-amber-700 ring-amber-200",
  PENDING: "bg-slate-50 text-slate-600 ring-slate-200",
  CREATED: "bg-slate-50 text-slate-600 ring-slate-200",
};

const STATUS_LABELS: Record<string, string> = {
  COLLECTED: "With agent",
  SUBMITTED: "Pending verification",
  BRANCH_RECEIVED: "At branch",
  APPROVED: "Approved",
  DEPOSITED: "Deposited",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        STATUS_COLORS[status] ?? "bg-slate-50 text-slate-600 ring-slate-200",
      )}
    >
      {label ?? STATUS_LABELS[status] ?? titleCase(status)}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={clsx("flex items-center justify-center py-12 text-slate-400", className)}>
      <Loader2 className="h-6 w-6 animate-spin" />
    </div>
  );
}

export function Empty({ children = "Nothing here yet." }: { children?: ReactNode }) {
  return <div className="py-12 text-center text-sm text-slate-400">{children}</div>;
}

export function Alert({ kind = "error", children }: { kind?: "error" | "warning" | "success" | "info"; children: ReactNode }) {
  const styles = {
    error: "bg-rose-50 text-rose-700 border-rose-200",
    warning: "bg-amber-50 text-amber-800 border-amber-200",
    success: "bg-emerald-50 text-emerald-700 border-emerald-200",
    info: "bg-sky-50 text-sky-700 border-sky-200",
  };
  return <div className={clsx("rounded-lg border px-3 py-2 text-sm", styles[kind])}>{children}</div>;
}

export function Field({ label, children, hint, className }: { label: string; children: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <label className={clsx("block", className)}>
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function Modal({ open, onClose, title, children, footer, wide }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className={clsx("max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white shadow-xl sm:rounded-2xl", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-4 px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function Table({ head, children, empty }: { head: ReactNode; children: ReactNode; empty?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100">
        <thead className="bg-slate-50/70">{head}</thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
      {empty && <Empty />}
    </div>
  );
}

export function Pagination({ page, count, pageSize = 25, onChange }: {
  page: number;
  count: number;
  pageSize?: number;
  onChange: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm text-slate-500">
      <span>
        Page {page} of {pages} · {count} records
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          Previous
        </Button>
        <Button variant="secondary" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}

export function Stat({ label, value, sub, tone = "default", icon }: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "default" | "good" | "warn" | "bad";
  icon?: ReactNode;
}) {
  const toneCls = { default: "text-slate-900", good: "text-emerald-700", warn: "text-amber-700", bad: "text-rose-700" }[tone];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <p className={clsx("mt-2 text-xl font-semibold tabular-nums", toneCls)}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export function Amount({ value, signed, className }: { value: string | null | undefined; signed?: boolean; className?: string }) {
  if (value === null || value === undefined) return <span className="text-slate-400">—</span>;
  const n = Number(value);
  const cls = signed ? (n > 0 ? "text-rose-600" : n < 0 ? "text-amber-600" : "text-emerald-600") : "";
  const fmt = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Math.abs(n));
  return <span className={clsx("tabular-nums", cls, className)}>{n < 0 && "−"}{fmt}</span>;
}
