import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

import { api, tokens } from "../api/client";
import type { Role, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<User>;
  logout: () => void;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(tokens.access));
  const qc = useQueryClient();

  useEffect(() => {
    if (!tokens.access) return;
    api
      .get<User>("/auth/me/")
      .then((r) => setUser(r.data))
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  const logout = useCallback(() => {
    const refresh = tokens.refresh;
    if (refresh) api.post("/auth/logout/", { refresh }).catch(() => undefined);
    tokens.clear();
    qc.clear();
    setUser(null);
  }, [qc]);

  useEffect(() => {
    const handler = () => logout();
    window.addEventListener("cmrs:logout", handler);
    return () => window.removeEventListener("cmrs:logout", handler);
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await api.post("/auth/login/", { username, password });
    tokens.set(data.access, data.refresh);
    setUser(data.user);
    return data.user as User;
  }, []);

  const hasRole = useCallback((...roles: Role[]) => Boolean(user && roles.includes(user.role)), [user]);

  return <AuthContext.Provider value={{ user, loading, login, logout, hasRole }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
