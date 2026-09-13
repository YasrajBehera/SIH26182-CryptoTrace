import { useCallback, createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getDataSource, setDataSource, isDemoMode } from "@/api/config";
import type { DataSource } from "@/api/config";
import { health } from "@/api/wallets";
import { hasValidToken } from "@/auth/tokenStore";

interface DataSourceContextValue {
  mode: DataSource;
  backendReachable: boolean;
  /** True when a non-expired live session token exists in the store. */
  sessionActive: boolean;
  checking: boolean;
  setMode: (mode: DataSource) => void;
  /** Live if backend health OK AND a valid session token exists; else demo. */
  isDemo: boolean;
}

const DataSourceContext = createContext<DataSourceContextValue | null>(null);

const AUTH_CHANGED_EVENT = "cryptotrace:authchanged";

export function DataSourceProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<DataSource>(getDataSource());
  const [backendReachable, setBackendReachable] = useState(false);
  const [checking, setChecking] = useState(true);
  const [sessionActive, setSessionActive] = useState<boolean>(() => hasValidToken());

  const negotiate = useCallback(async () => {
    const ok = await health.check();
    const authed = hasValidToken();
    setSessionActive(authed);
    setBackendReachable(ok);
    // Live data requires both a reachable backend AND a live session token.
    // A public health OK alone is NOT enough — the protected endpoints the
    // dashboard drives would 401, which previously left the user on a
    // misleading "Backend connected — Live" state with dead data.
    const next: DataSource = ok && authed ? "live" : "demo";
    setDataSource(next);
    setModeState(next);
    setChecking(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void negotiate();
    // Re-negotiate whenever authentication state changes (login / logout /
    // expired token) so the mode flips between demo and live immediately.
    const onAuthChanged = () => {
      if (!cancelled) void negotiate();
    };
    window.addEventListener(AUTH_CHANGED_EVENT, onAuthChanged);
    window.addEventListener("cryptotrace:unauthorized", onAuthChanged);
    return () => {
      cancelled = true;
      window.removeEventListener(AUTH_CHANGED_EVENT, onAuthChanged);
      window.removeEventListener("cryptotrace:unauthorized", onAuthChanged);
    };
  }, [negotiate]);

  const setMode = useCallback((next: DataSource) => {
    setDataSource(next);
    setModeState(next);
  }, []);

  const value = useMemo<DataSourceContextValue>(
    () => ({
      mode,
      backendReachable,
      sessionActive,
      checking,
      setMode,
      isDemo: isDemoMode(),
    }),
    [mode, backendReachable, sessionActive, checking, setMode],
  );

  return <DataSourceContext.Provider value={value}>{children}</DataSourceContext.Provider>;
}

export function useDataSource(): DataSourceContextValue {
  const ctx = useContext(DataSourceContext);
  if (!ctx) throw new Error("useDataSource must be used within <DataSourceProvider>");
  return ctx;
}