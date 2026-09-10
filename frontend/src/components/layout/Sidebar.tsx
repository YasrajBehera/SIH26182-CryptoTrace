import { NavLink } from "react-router-dom";
import {
  AuditIcon,
  CasesIcon,
  DashboardIcon,
  EvidenceIcon,
  GraphIcon,
  LogoutIcon,
  ReportIcon,
  RiskIcon,
  SettingsIcon,
  ShieldIcon,
  TxIcon,
  UsersIcon,
  VaspIcon,
  WalletIcon,
} from "@/components/icons";
import type { Permission } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { useDataSource } from "@/app/DataSourceContext";
import { Badge } from "@/components/ui";

interface NavEntry {
  to: string;
  label: string;
  icon: React.ReactNode;
  end?: boolean;
  badge?: string;
  permission?: string;
}

const MAIN_NAV: NavEntry[] = [
  { to: "/dashboard", label: "Dashboard", icon: <DashboardIcon />, end: true },
  { to: "/investigations", label: "Investigations", icon: <CasesIcon />, permission: "investigation.read" },
  { to: "/wallets", label: "Investigate Wallet", icon: <WalletIcon />, permission: "wallet.read" },
  { to: "/transactions", label: "Transactions", icon: <TxIcon />, permission: "wallet.read" },
  { to: "/graph", label: "Transaction Graph", icon: <GraphIcon />, badge: "stub", permission: "graph.read" },
  { to: "/vasp", label: "VASP Attribution", icon: <VaspIcon />, badge: "stub", permission: "attribution.read" },
  { to: "/evidence", label: "Evidence", icon: <EvidenceIcon />, permission: "evidence.read" },
  { to: "/risk", label: "Risk Analysis", icon: <RiskIcon />, permission: "risk.read" },
  { to: "/reports", label: "Reports", icon: <ReportIcon />, permission: "report.export" },
  { to: "/audit", label: "Audit Logs", icon: <AuditIcon />, permission: "audit.read" },
];

const ADMIN_NAV: NavEntry[] = [
  { to: "/admin/users", label: "Users", icon: <UsersIcon />, permission: "user.manage" },
  { to: "/admin/roles", label: "Roles & Permissions", icon: <ShieldIcon />, permission: "user.manage" },
  { to: "/admin/settings", label: "System Settings", icon: <SettingsIcon />, permission: "user.manage" },
];

function NavItems({ entries, can }: { entries: NavEntry[]; can: (permission: Permission) => boolean }) {
  const permitted = (e: NavEntry) => !e.permission || can(e.permission as Permission);
  return (
    <>
      {entries
        .filter(permitted)
        .map((e) => (
          <NavLink
            key={e.to}
            to={e.to}
            end={e.end}
            className={({ isActive }) => `sidebar-link ${isActive ? "active" : ""}`}
          >
            {e.icon}
            {e.label}
            {e.badge ? <span className="nav-badge">{e.badge}</span> : null}
          </NavLink>
        ))}
    </>
  );
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout, can } = useAuth();
  const { mode, backendReachable } = useDataSource();

  const backendStatusEl =
    mode === "live" ? (
      <div className="sidebar-status">
        <span className="status-dot ok" aria-hidden />
        <span>Backend connected</span>
        <Badge className="status-success">Live</Badge>
      </div>
    ) : (
      <div className="sidebar-status">
        <span className="status-dot error" aria-hidden />
        <span>Backend unavailable</span>
        <Badge className="badge-demo">Demo</Badge>
      </div>
    );

  void backendReachable;

  const adminEntries = ADMIN_NAV.filter((e) => !e.permission || can(e.permission as Permission));

  return (
    <>
      {open ? <div className="sidebar-overlay open" onClick={onClose} aria-hidden /> : null}
      <aside className={`app-sidebar ${open ? "open" : ""}`} aria-label="Primary navigation">
        <div className="sidebar-brand">
          <div className="sidebar-brand-mark" aria-hidden>
            <svg viewBox="0 0 32 32" width="18" height="18">
              <path d="M16 5 27 15.5 16 26 5 15.5Z" fill="none" stroke="#fff" strokeWidth="2" />
              <circle cx="16" cy="15.5" r="3" fill="#38bdf8" />
            </svg>
          </div>
          <div>
            <div className="sidebar-brand-title">CryptoTrace</div>
            <div className="sidebar-brand-sub">Investigation Platform</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="sidebar-section-label">Workspace</div>
          <NavItems entries={MAIN_NAV} can={can} />

          {adminEntries.length ? (
            <>
              <div className="sidebar-section-label">System</div>
              <NavItems entries={adminEntries} can={can} />
            </>
          ) : null}
        </nav>

        <div className="sidebar-footer">
          {user ? (
            <div className="sidebar-user">
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: "var(--text-sm)" }}>{user.name}</div>
                <div style={{ fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{user.title}</div>
              </div>
              <Badge className="status-open" style={{ textTransform: "capitalize", flex: "0 0 auto" }}>
                {user.role.replace(/_/g, " ")}
              </Badge>
              <button
                className="btn btn-ghost btn-icon btn-sm"
                onClick={() => logout()}
                aria-label="Log out"
                title="Log out"
                style={{ marginLeft: "auto" }}
              >
                <LogoutIcon />
              </button>
            </div>
          ) : null}
          {backendStatusEl}
        </div>
      </aside>
    </>
  );
}