import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import type { ApiError } from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const ACCESS = "cmrs.access";
const REFRESH = "cmrs.refresh";

export const tokens = {
  get access() {
    return sessionStorage.getItem(ACCESS);
  },
  get refresh() {
    return sessionStorage.getItem(REFRESH);
  },
  set(access: string, refresh?: string) {
    sessionStorage.setItem(ACCESS, access);
    if (refresh) sessionStorage.setItem(REFRESH, refresh);
  },
  clear() {
    sessionStorage.removeItem(ACCESS);
    sessionStorage.removeItem(REFRESH);
  },
};

export const api = axios.create({ baseURL: `${BASE}/api`, timeout: 20000 });

api.interceptors.request.use((config) => {
  const t = tokens.access;
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  const refresh = tokens.refresh;
  if (!refresh) return null;
  try {
    const { data } = await axios.post(`${BASE}/api/auth/refresh/`, { refresh });
    tokens.set(data.access, data.refresh);
    return data.access as string;
  } catch {
    tokens.clear();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isAuthCall = original?.url?.includes("/auth/");
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      refreshing ??= refreshAccess().finally(() => (refreshing = null));
      const access = await refreshing;
      if (access) {
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      }
      window.dispatchEvent(new Event("cmrs:logout"));
    }
    return Promise.reject(error);
  },
);

export function errorOf(err: unknown): ApiError {
  const e = err as AxiosError<ApiError>;
  if (e?.response?.data && typeof e.response.data === "object" && "message" in e.response.data) {
    return e.response.data;
  }
  if (e?.code === "ECONNABORTED" || e?.message === "Network Error") {
    return { code: "network", message: "Cannot reach the server. Check your connection.", details: null };
  }
  return { code: "unknown", message: "Something went wrong.", details: null };
}

/** Flatten DRF field errors ({field: [msg]}) into a single readable string. */
export function errorText(err: unknown): string {
  const e = errorOf(err);
  if (e.code === "validation_error" && e.details && typeof e.details === "object") {
    const parts = Object.entries(e.details as Record<string, unknown>).map(
      ([k, v]) => `${k === "non_field_errors" ? "" : `${k.replace(/_/g, " ")}: `}${Array.isArray(v) ? v.join(" ") : String(v)}`,
    );
    return parts.join(" · ") || e.message;
  }
  return e.message;
}
