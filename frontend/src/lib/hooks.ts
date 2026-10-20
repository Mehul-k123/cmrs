import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { Branch, Paginated, User } from "../api/types";

export type Params = Record<string, string | number | boolean | undefined | null>;

export function clean(params: Params): Record<string, string> {
  return Object.fromEntries(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== "")
      .map(([k, v]) => [k, String(v)]),
  );
}

export function useList<T>(path: string, params: Params = {}, enabled = true) {
  const p = clean(params);
  return useQuery({
    queryKey: [path, p],
    queryFn: async () => (await api.get<Paginated<T>>(path, { params: p })).data,
    enabled,
    placeholderData: (prev) => prev,
  });
}

export function useOne<T>(path: string | null) {
  return useQuery({
    queryKey: [path],
    queryFn: async () => (await api.get<T>(path!)).data,
    enabled: Boolean(path),
  });
}

export function useBranches(enabled = true) {
  return useList<Branch>("/branches/", { page_size: 200 }, enabled);
}

export function useAgents(branch?: number | string | null, enabled = true) {
  return useList<User>("/auth/users/", { role: "AGENT", branch, page_size: 200 }, enabled);
}
