import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { useDataSource } from "@/app/DataSourceContext";
import { Modal } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isDemo } = useDataSource();
  const { sessionExpired, logout } = useAuth();

  return (
    <div className="app-frame">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="app-main">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
      </div>
      <main className="app-content">
        {isDemo ? (
          <div className="demo-banner no-print" role="status" style={{ borderRadius: 0, border: 0, borderBottom: "1px solid rgba(245,165,36,0.35)" }}>
            <span aria-hidden>DEMO DATA</span>
            <span style={{ fontWeight: 400, opacity: 0.85 }}>
              The backend is unreachable or a feature has no backend yet. A visible indicator is shown whenever data is synthetic.
            </span>
          </div>
        ) : (
          <div className="demo-banner no-print" role="status" style={{ borderRadius: 0, border: 0, borderBottom: "1px solid rgba(47,212,139,0.35)", background: "linear-gradient(90deg, rgba(47,212,139,0.14), rgba(47,212,139,0.04))", color: "#7ce8b8" }}>
            <span aria-hidden>● LIVE</span>
            <span style={{ fontWeight: 400, opacity: 0.9 }}>
              Connected to CryptoTrace API. Wallet transfers are live; graph/attribution features remain demo stubs.
            </span>
          </div>
        )}
        <Outlet />
      </main>

      {/* Session timeout: demo auth warning only — backend auth will enforce for real */}
      <Modal
        open={sessionExpired}
        onClose={() => logout("session_expired")}
        title="Session expired"
        footer={
          <>
            <button className="btn btn-primary" onClick={() => logout("session_expired")}>
              Log in again
            </button>
          </>
        }
      >
        <p style={{ margin: 0 }}>
          Your session has been inactive for more than 30 minutes and was locked for safety. This is a demo
          session mechanism; real session enforcement must run on the backend.
        </p>
      </Modal>
    </div>
  );
}