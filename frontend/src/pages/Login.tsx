import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { errorText } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, Button, Field } from "../components/ui";

const DEMO = [
  ["admin", "Admin"],
  ["finance", "Finance"],
  ["bm.mumbai", "Branch Manager (Mumbai)"],
  ["agent.ravi", "Agent (Mumbai)"],
  ["bm.pune", "Branch Manager (Pune)"],
  ["agent.arjun", "Agent (Pune)"],
];

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      nav("/", { replace: true });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-brand-900 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center text-white">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-2xl font-bold">₹</div>
          <h1 className="text-2xl font-semibold">CMRS</h1>
          <p className="text-sm text-slate-300">Cash Management & Reconciliation System</p>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl bg-white p-6 shadow-xl">
          {error && <Alert>{error}</Alert>}
          <Field label="Username">
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required autoFocus />
          </Field>
          <Field label="Password">
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </Field>
          <Button type="submit" loading={busy} className="w-full">
            Sign in
          </Button>
          <div className="border-t border-slate-100 pt-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Demo accounts · password Demo@1234</p>
            <div className="flex flex-wrap gap-1.5">
              {DEMO.map(([u, label]) => (
                <button
                  type="button"
                  key={u}
                  onClick={() => {
                    setUsername(u);
                    setPassword("Demo@1234");
                  }}
                  className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:border-brand-500 hover:text-brand-700"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
