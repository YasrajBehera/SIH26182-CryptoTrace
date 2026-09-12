import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { AppUser, Permission, Role } from "@/api/types";
import { canRole } from "./permissions";
import { demoCredentials, demoUsers } from "@/mock/users";
import { auth as backendAuth } from "@/api/auth";
import { clearToken, getToken, hasValidToken } from "./tokenStore";

/**
 * Auth provider with a two-tier strategy:
 *
 * 1. LIVE: when the backend is reachable, `login` calls POST /api/v1/auth/login,
 *    persists the bearer token, and resolves the session from the server.
 * 2. DEMO: when the backend is unreachable (or creds are demo-only), it falls
 *    back to the documented demo accounts so the RBAC UI remains demoable.
 *
 * The UI label "DEMO AUTH" is only shown when the resolved session came from
 * the demo path. The backend remains the authorization authority in live mode.
 *
 * Session is stored in sessionStorage (cleared when the tab closes) and never
 * holds credentials — only the user profile and (in live mode) the opaque
 * bearer token. No secrets are ever persisted.
 */

const SESSION_KEY = "cryptotrace.session";
const IDLE_TIMEOUT_MS = 30 * 60_000; // 30 minutes

interface StoredSession {
  user: AppUser;
  isDemoAuth: boolean;
  startedAt: string;
}

interface AuthContextValue {
  user: AppUser | null;
  role: Role | null;
  username: string | null;
  isAuthenticated: boolean;
  isDemoAuth: boolean;
  login: (username: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  logout: (reason?: string) => void;
  can: (permission: Permission) => boolean;
  idleSecondsRemaining: number;
  sessionExpired: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readSession(): StoredSession | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    if (!parsed.user || !parsed.user.id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const initial = readSession();
  const [user, setUser] = useState<AppUser | null>(initial?.user ?? null);
  const [isDemoAuth, setIsDemoAuth] = useState<boolean>(initial?.isDemoAuth ?? true);
  const [lastActive, setLastActive] = useState<number>(() => Date.now());
  const [sessionExpired, setSessionExpired] = useState(false);

  const role = user?.role ?? null;
  const username = user?.username ?? user?.name ?? null;

  // Idle tracking for session-timeout UI
  useEffect(() => {
    const bump = () => setLastActive(Date.now());
    const events: Array<keyof WindowEventMap> = ["mousemove", "keydown", "click", "scroll"];
    events.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    return () => events.forEach((e) => window.removeEventListener(e, bump));
  }, []);

  useEffect(() => {
    if (!user) return;
    const interval = window.setInterval(() => {
      const idle = Date.now() - lastActive;
      if (idle > IDLE_TIMEOUT_MS) {
        setSessionExpired(true);
        window.clearInterval(interval);
      }
    }, 5000);
    return () => window.clearInterval(interval);
  }, [user, lastActive]);

  const idleSecondsRemaining = useMemo(() => {
    if (!user) return 0;
    return Math.max(0, Math.round((IDLE_TIMEOUT_MS - (Date.now() - lastActive)) / 1000));
  }, [user, lastActive]);

  const persist = useCallback((nextUser: AppUser, nextIsDemo: boolean) => {
    setUser(nextUser);
    setIsDemoAuth(nextIsDemo);
    setLastActive(Date.now());
    setSessionExpired(false);
    try {
      const session: StoredSession = {
        user: nextUser,
        isDemoAuth: nextIsDemo,
        startedAt: new Date().toISOString(),
      };
      window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    } catch {
      // storage unavailable — session stays in memory
    }
  }, []);

  const login = useCallback(
    async (name: string, password: string) => {
      setLastActive(Date.now());
      setSessionExpired(false);

      // 1) Try the real backend.
      const live = await backendAuth.login(name, password);
      if (live.ok && live.user) {
        persist(live.user, false);
        return { ok: true };
      }

      // 2) Demo fallback (backend offline or demo-only credentials).
      const cred = demoCredentials.find(
        (c) => c.username.toLowerCase() === name.trim().toLowerCase(),
      );
      if (!cred || cred.password !== password) {
        return {
          ok: false,
          error:
            live.error === "Authorization is required to access this resource."
              ? live.error
              : "Invalid credentials. See the login page hint for demo logins.",
        };
      }
      const demoUser = demoUsers.find((u) => u.id === cred.userId);
      if (!demoUser) {
        return { ok: false, error: "Demo account not found." };
      }
      // Drop any stale live token before switching to a demo session so live
      // requests never attach an expired credential.
      clearToken();
      persist(demoUser, true);
      return { ok: true };
    },
    [persist],
  );

  const logout = useCallback((_reason?: string) => {
    void _reason;
    try {
      window.sessionStorage.removeItem(SESSION_KEY);
    } catch {
      // ignore
    }
    // Best-effort server-side logout; token discarded regardless.
    if (getToken()) {
      backendAuth.logout();
    } else {
      clearToken();
    }
    setUser(null);
    setIsDemoAuth(true);
    setSessionExpired(false);
  }, []);

  // Restore token validity on boot: if a live token exists but is expired,
  // clear it. Keep the demo session otherwise.
  useEffect(() => {
    if (getToken() && !hasValidToken()) {
      clearToken();
      if (isDemoAuth) {
        // expired live token with no demo session — force re-login
        setUser(null);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A 401 from the backend means the presented token is no longer valid.
  // Clear the live session so the user re-authenticates instead of hitting
  // dead "Authorization required" screens. Demo sessions carry no token and
  // never receive 401s, so they are ignored.
  useEffect(() => {
    const onUnauthorized = () => {
      if (user && !isDemoAuth) {
        logout("session_expired");
      }
    };
    window.addEventListener("cryptotrace:unauthorized", onUnauthorized);
    return () => window.removeEventListener("cryptotrace:unauthorized", onUnauthorized);
  }, [user, isDemoAuth, logout]);

  const can = useCallback((permission: Permission) => canRole(role, permission), [role]);

  const value: AuthContextValue = {
    user,
    role,
    username,
    isAuthenticated: !!user,
    isDemoAuth,
    login,
    logout,
    can,
    idleSecondsRemaining,
    sessionExpired,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}