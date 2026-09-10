import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { AppUser, Permission, Role } from "@/api/types";
import { canRole } from "./permissions";
import { demoCredentials, demoUsers } from "@/mock/users";

/**
 * Mock authentication provider.
 *
 * AUTH IS NOT YET IMPLEMENTED ON THE BACKEND. This provider simulates login
 * so the security UI (session, RBAC, logout) can be built and demoed. Real
 * authentication must come from the backend; nothing here authorizes requests.
 *
 * Session is stored in sessionStorage (cleared when the tab closes) and never
 * holds credentials — only a user id. No secrets are ever persisted.
 */

const SESSION_KEY = "cryptotrace.session";
const IDLE_TIMEOUT_MS = 30 * 60_000; // 30 minutes

interface Session {
  userId: string;
  startedAt: string;
}

interface AuthContextValue {
  user: AppUser | null;
  role: Role | null;
  isAuthenticated: boolean;
  isDemoAuth: boolean;
  login: (username: string, password: string) => { ok: boolean; error?: string };
  logout: (reason?: string) => void;
  can: (permission: Permission) => boolean;
  idleSecondsRemaining: number;
  sessionExpired: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readSession(): Session | null {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    if (!parsed.userId) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState<string | null>(() => readSession()?.userId ?? null);
  const [lastActive, setLastActive] = useState<number>(() => Date.now());
  const [sessionExpired, setSessionExpired] = useState(false);

  const user = useMemo(() => demoUsers.find((u) => u.id === userId) ?? null, [userId]);
  const role = user?.role ?? null;

  // Idle tracking for session-timeout UI
  useEffect(() => {
    const bump = () => setLastActive(Date.now());
    const events: Array<keyof WindowEventMap> = ["mousemove", "keydown", "click", "scroll"];
    events.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    return () => events.forEach((e) => window.removeEventListener(e, bump));
  }, []);

  useEffect(() => {
    if (!userId) return;
    const interval = window.setInterval(() => {
      const idle = Date.now() - lastActive;
      if (idle > IDLE_TIMEOUT_MS) {
        setSessionExpired(true);
        window.clearInterval(interval);
      }
    }, 5000);
    return () => window.clearInterval(interval);
  }, [userId, lastActive]);

  const idleSecondsRemaining = useMemo(() => {
    if (!userId) return 0;
    return Math.max(0, Math.round((IDLE_TIMEOUT_MS - (Date.now() - lastActive)) / 1000));
  }, [userId, lastActive]);

  const login = useCallback((username: string, password: string) => {
    const cred = demoCredentials.find(
      (c) => c.username.toLowerCase() === username.trim().toLowerCase(),
    );
    if (!cred || cred.password !== password) {
      return { ok: false, error: "Invalid demo credentials. See the login page hint for demo logins." };
    }
    const session: Session = { userId: cred.userId, startedAt: new Date().toISOString() };
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    setUserId(cred.userId);
    setLastActive(Date.now());
    setSessionExpired(false);
    return { ok: true };
  }, []);

  const logout = useCallback((_reason?: string) => {
    window.sessionStorage.removeItem(SESSION_KEY);
    setUserId(null);
    setSessionExpired(false);
  }, []);

  const can = useCallback((permission: Permission) => canRole(role, permission), [role]);

  useEffect(() => {
    if (!userId) return;
    const session: Session = { userId, startedAt: new Date().toISOString() };
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }, [userId]);

  const value: AuthContextValue = {
    user,
    role,
    isAuthenticated: !!user,
    isDemoAuth: true,
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