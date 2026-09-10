import { PageHeader, Button, Card, DemoBadge, Badge, Switch, Select, Field } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import { useDataSource } from "@/app/DataSourceContext";
import { useToast } from "@/components/ui";
import { useState } from "react";

export function SettingsPage() {
  const { can, role, user } = useAuth();
  const { mode, backendReachable, checking, setMode } = useDataSource();
  const { push } = useToast();
  const [defaultNetwork, setDefaultNetwork] = useState("Ethereum");
  const [demosEnabled, setDemosEnabled] = useState(true);

  if (!can("settings.manage")) {
    return (
      <div className="page">
        <PageHeader title="System Settings" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>
            Your role ({role}) does not permit changing system settings. Settings management ships with backend auth.
          </p>
        </Card>
      </div>
    );
  }

  const save = () => {
    push({ kind: "ok", title: "Settings saved (demo)", description: "Settings are stored in memory only in this release." });
  };

  return (
    <div className="page">
      <PageHeader
        title="System Settings"
        subtitle="Data source, defaults, and platform behavior."
        crumbs={[{ label: "Administration" }, { label: "System Settings" }]}
        actions={<DemoBadge />}
      />

      <Card title="Data source">
        <div className="stack">
          <div className="detail-row">
            <span className="detail-label">Backend reachability</span>
            <span className="detail-value">
              {checking ? (
                "Checking…"
              ) : backendReachable ? (
                <Badge className="status-success">Live (FastAPI reachable)</Badge>
              ) : (
                <Badge className="status-draft">Unavailable — demo mode active</Badge>
              )}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Active mode</span>
            <span className="detail-value">
              <Badge className={mode === "live" ? "status-success" : "badge-demo"} data-testid="settings-mode">
                {mode}
              </Badge>
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Manual override</span>
            <span className="detail-value">
              <Switch
                checked={mode === "live"}
                onChange={(on) => {
                  setMode(on ? "live" : "demo");
                  push({
                    kind: "info",
                    title: `Switched to ${on ? "live" : "demo"} mode`,
                    description: on
                      ? "Live wallet queries now target the backend. Unsupported features surface empty/awaiting states."
                      : "All data is now labeled synthetic demo data.",
                  });
                }}
                label="Prefer live backend"
              />
            </span>
          </div>
        </div>
      </Card>

      <Card title="Defaults">
        <div className="stack">
          <Field label="Default network" htmlFor="set-network">
            <Select id="set-network" value={defaultNetwork} onChange={(e) => setDefaultNetwork(e.target.value)} style={{ maxWidth: 240 }}>
              <option>Ethereum</option>
              <option>Polygon</option>
              <option>Arbitrum</option>
              <option>Optimism</option>
            </Select>
          </Field>
          <div className="detail-row">
            <span className="detail-label">Show demo data indicators</span>
            <span className="detail-value">
              <Switch checked={demosEnabled} onChange={setDemosEnabled} label="Always mark synthetic records as DEMO" />
            </span>
          </div>
        </div>
      </Card>

      <Card title="Session">
        <div className="stack">
          <div className="detail-row">
            <span className="detail-label">Signed in as</span>
            <span className="detail-value">{user?.name ?? "No active session"}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Role</span>
            <span className="detail-value">
              <Badge className="status-open">{role}</Badge>
            </span>
          </div>
        </div>
      </Card>

      <Card title="Software">
        <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "var(--text-sm)" }}>
          Frontend contract: <span className="mono">Member 4 · SIH26182-CryptoTrace</span>. Demo environment —
          nothing on this screen is real intelligence.
        </p>
      </Card>

      <div className="row">
        <Button variant="primary" onClick={save}>
          Save settings
        </Button>
      </div>
    </div>
  );
}