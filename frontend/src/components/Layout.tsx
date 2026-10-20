import clsx from "clsx";
import {
  AlertTriangle,
  Banknote,
  ClipboardCheck,
  FileClock,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  ReceiptIndianRupee,
  Send,
  Smartphone,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";

import type { Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { titleCase } from "../lib/format";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  roles: Role[];
}

const ic = "h-4 w-4";
const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: <LayoutDashboard className={ic} />, roles: ["ADMIN", "FINANCE", "BRANCH_MANAGER", "AGENT"] },
  { to: "/customers", label: "Customers & Loans", icon: <Users className={ic} />, roles: ["ADMIN", "FINANCE", "BRANCH_MANAGER", "AGENT"] },
  { to: "/collect", label: "Record Collection", icon: <ReceiptIndianRupee className={ic} />, roles: ["AGENT"] },
  { to: "/daily", label: "Daily Collections", icon: <Wallet className={ic} />, roles: ["AGENT"] },
  { to: "/submit", label: "Submit Cash", icon: <Send className={ic} />, roles: ["AGENT"] },
  { to: "/collections", label: "All Collections", icon: <Banknote className={ic} />, roles: ["ADMIN", "FINANCE", "BRANCH_MANAGER"] },
  { to: "/submissions", label: "Cash Submissions", icon: <ClipboardCheck className={ic} />, roles: ["ADMIN", "FINANCE", "BRANCH_MANAGER", "AGENT"] },
  { to: "/discrepancies", label: "Discrepancies", icon: <AlertTriangle className={ic} />, roles: ["ADMIN", "FINANCE", "BRANCH_MANAGER"] },
  { to: "/deposits", label: "Bank Deposits", icon: <Landmark className={ic} />, roles: ["ADMIN", "FINANCE", "BRANCH_MANAGER"] },
  { to: "/payments", label: "UPI Payments", icon: <Smartphone className={ic} />, roles: ["ADMIN", "FINANCE", "BRANCH_MANAGER", "AGENT"] },
  { to: "/audit", label: "Audit Log", icon: <FileClock className={ic} />, roles: ["ADMIN", "FINANCE"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  if (!user) return null;
  const items = NAV.filter((n) => n.roles.includes(user.role));

  const sidebar = (
    <nav className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-lg font-bold text-white">₹</div>
        <div>
          <p className="text-sm font-semibold text-white">CMRS</p>
          <p className="text-[11px] text-slate-400">Cash Management & Reconciliation</p>
        </div>
      </div>
      <div className="flex-1 space-y-0.5 px-3">
        {items.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                isActive ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white",
              )
            }
          >
            {n.icon}
            {n.label}
          </NavLink>
        ))}
      </div>
      <div className="border-t border-white/10 p-4">
        <p className="truncate text-sm font-medium text-white">{user.display_name}</p>
        <p className="truncate text-xs text-slate-400">
          {titleCase(user.role)}
          {user.branch_name ? ` · ${user.branch_name}` : ""}
        </p>
        <button onClick={logout} className="mt-3 flex items-center gap-2 text-xs text-slate-300 hover:text-white">
          <LogOut className="h-3.5 w-3.5" /> Sign out
        </button>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 hidden w-64 bg-slate-900 lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-slate-900">{sidebar}</aside>
        </div>
      )}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <button onClick={() => setOpen((o) => !o)} aria-label="Menu" className="rounded p-1 text-slate-600">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
        <span className="text-sm font-semibold">CMRS</span>
        <span className="w-6" />
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
