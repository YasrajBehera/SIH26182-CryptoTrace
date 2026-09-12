import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Field, Input, Button, Card } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import { allDemoRoles } from "@/mock/users";

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [trying, setTrying] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  if (isAuthenticated) return <Navigate to={from} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setTrying(true);
    const result = await login(username, password);
    setTrying(false);
    if (!result.ok) {
      setError(result.error ?? "Login failed.");
      return;
    }
    navigate(from, { replace: true });
  };

  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div className="sidebar-brand-mark" style={{ width: 44, height: 44, margin: "0 auto 12px", fontSize: 20 }}>
            <svg viewBox="0 0 32 32" width="24" height="24">
              <path d="M16 5 27 15.5 16 26 5 15.5Z" fill="none" stroke="#fff" strokeWidth="2" />
              <circle cx="16" cy="15.5" r="3" fill="#38bdf8" />
            </svg>
          </div>
          <h1 style={{ margin: 0 }}>CryptoTrace</h1>
          <p style={{ color: "var(--text-muted)", margin: "4px 0 0" }}>
            Blockchain Investigation &amp; Financial Intelligence Platform
          </p>
        </div>

        <Card>
          <form className="stack" onSubmit={submit}>
            <Field label="Username" htmlFor="login-user">
              <Input
                id="login-user"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. admin"
                required
              />
            </Field>
            <Field label="Password" htmlFor="login-pass">
              <Input
                id="login-pass"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </Field>
            {error ? (
              <div className="field-error" role="alert">
                {error}
              </div>
            ) : null}
            <Button variant="primary" type="submit" block disabled={trying}>
              {trying ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>

        <Card style={{ marginTop: 16 }}>
          <p style={{ margin: "0 0 8px", fontWeight: 600, fontSize: "var(--text-sm)" }}>
            Demo access — Production users are created by an administrator.
          </p>
          <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            Login attempts hit the backend first (POST /api/v1/auth/login). If it is offline you can sign in with any
            of these demo accounts (password: <code>cryptotrace-demo</code>):
          </p>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: "var(--text-xs)", color: "var(--text-muted)" }}>
            {allDemoRoles().map((r) => (
              <li key={r}>{r.replace(/_/g, " ")}</li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}