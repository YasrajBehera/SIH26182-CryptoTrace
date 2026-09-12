import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { BellIcon, MenuIcon } from "@/components/icons";
import { useAuth } from "@/auth/AuthContext";
import { useDataSource } from "@/app/DataSourceContext";
import { Dropdown, Badge } from "@/components/ui";
import { GlobalSearch } from "./GlobalSearch";

const NETWORKS = [
  { value: "eth", label: "Ethereum Mainnet" },
  { value: "eth-sepolia", label: "Sepolia Testnet" },
];

const DEMO_NOTIFICATIONS = [
  { id: "n1", title: "Risk escalated — CT-2026-0141", meta: "Just now · system" },
  { id: "n2", title: "New VASP candidate detected", meta: "12m ago · attribution engine" },
  { id: "n3", title: "Evidence E-021 attached", meta: "18m ago · Rohan Iyer" },
];

export function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { user, username, logout, role } = useAuth();
  const { mode } = useDataSource();
  const [network, setNetwork] = useState("eth");
  const navigate = useNavigate();

  return (
    <header className="topbar">
      <button className="topbar-sidebar-toggle" onClick={onMenuClick} aria-label="Toggle navigation">
        <MenuIcon />
      </button>

      <GlobalSearch />

      <div className="topbar-actions">
        <select
          className="topbar-select network"
          value={network}
          onChange={(e) => setNetwork(e.target.value)}
          aria-label="Network selector"
        >
          {NETWORKS.map((n) => (
            <option key={n.value} value={n.value}>
              {n.label}
            </option>
          ))}
        </select>

        <span className={`env-chip ${mode === "live" ? "live" : "demo"}`} role="status" aria-label={mode === "live" ? "Live backend connected" : "Demo / synthetic mode"}>
          <span className="status-dot" aria-hidden />
          {mode === "live" ? "LIVE" : "DEMO / SYNTHETIC"}
        </span>

        <Dropdown
          label="Notifications"
          trigger={<span className="row" style={{ gap: 6 }}><BellIcon /> <Badge className="status-open">3</Badge></span>}
          items={[
            { key: "__h", label: "Notifications (demo)", onClick: () => undefined },
            { key: "__sep" },
            ...DEMO_NOTIFICATIONS.map((n) => ({
              key: n.id,
              label: n.title,
              icon: <span className="status-dot" />,
              onClick: () => undefined,
            })),
          ]}
        />

        <Dropdown
          label="User menu"
          trigger={<span>{username ?? "User"} · {role?.replace("_", " ") ?? "—"}</span>}
          items={[
            { key: "__h", label: `${user?.name ?? ""}${user?.name ? " — " : ""}${user?.title ?? ""}` },
            { key: "__sep" },
            { key: "profile", label: "Profile", onClick: () => navigate("/admin/settings") },
            { key: "mode", label: mode === "live" ? "Data source: Live" : "Data source: Demo", onClick: () => navigate("/dashboard") },
            { key: "__sep" },
            { key: "logout", label: "Log out", danger: true, onClick: () => logout() },
          ]}
        />
      </div>
    </header>
  );
}