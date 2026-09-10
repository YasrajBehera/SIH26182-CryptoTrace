import { useCallback, createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getDataSource, setDataSource, isDemoMode } from "@/api/config";
import type { DataSource } from "@/api/config";
import { health } from "@/api/wallets";

interface DataSourceContextValue {
  mode: DataSource;
  backendReachable: boolean;
  checking: boolean;
  setMode: (mode: DataSource) => void;
  /** Live if backend health OK; else demo. Manual override allowed via setMode. */
  isDemo: boolean;
}

const DataSourceContext = createContext<DataSourceContextValue | null>(null);

export function DataSourceProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<DataSource>(getDataSource());
  const [backendReachable, setBackendReachable] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ok = await health.check();
      if (cancelled) return;
      setBackendReachable(ok);
      const next: DataSource = ok ? "live" : "demo";
      setDataSource(next);
      setModeState(next);
      setChecking(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setMode = useCallback((next: DataSource) => {
    setDataSource(next);
    setModeState(next);
  }, []);

  const value = useMemo<DataSourceContextValue>(
    () => ({
      mode,
      backendReachable,
      checking,
      setMode,
      isDemo: isDemoMode(),
    }),
    [mode, backendReachable, checking, setMode],
  );

  return <DataSourceContext.Provider value={value}>{children}</DataSourceContext.Provider>;
}

export function useDataSource(): DataSourceContextValue {
  const ctx = useContext(DataSourceContext);
  if (!ctx) throw new Error("useDataSource must be used within <DataSourceProvider>");
  return ctx;
}