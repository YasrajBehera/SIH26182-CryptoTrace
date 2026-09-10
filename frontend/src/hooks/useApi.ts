import { useCallback, useEffect, useRef, useState } from "react";

interface UseApiOptions {
  /** When false, the query is not executed and `loading` stays false. Default true. */
  enabled?: boolean;
}

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  setData: (data: T) => void;
}

/**
 * Tiny async-data hook. Keeps server/async state separate from UI state.
 * Errors are always user-safe strings (see api/client.ts).
 */
export function useApi<T>(fn: () => Promise<T>, deps: readonly unknown[] = [], options: UseApiOptions = {}): UseApiResult<T> {
  const { enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fnRef.current().then(
      (result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      },
      (err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : "The service could not be reached.";
        setError(message);
        setData(null);
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, enabled]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  return { data, loading, error, reload, setData };
}