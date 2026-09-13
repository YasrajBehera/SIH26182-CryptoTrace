import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ToastProvider, SkeletonTitle, SkeletonBlock, UnauthorizedState } from "@/components/ui";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { DataSourceProvider } from "@/app/DataSourceContext";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { AppShell } from "@/components/layout/AppShell";
import type { Permission } from "@/api/types";

/**
 * Route-level code splitting. The graph page pulls in @xyflow/react (~200kB),
 * so it is isolated from the initial bundle. Every route gets a lightweight
 * skeleton fallback while its chunk loads.
 */
const lazyPage = (loader: () => Promise<{ [key: string]: unknown }>, name: string) => {
  const Component = lazy(() =>
    loader().then((mod) => ({ default: mod[name] as React.ComponentType })),
  );
  Object.assign(Component, { displayName: name });
  return Component;
};

const LoginPage = lazyPage(() => import("@/features/auth/LoginPage"), "LoginPage");
const SearchPage = lazyPage(() => import("@/features/search/SearchPage"), "SearchPage");
const DashboardPage = lazyPage(() => import("@/features/dashboard/DashboardPage"), "DashboardPage");
const CasesPage = lazyPage(() => import("@/features/investigations/CasesPage"), "CasesPage");
const NewCasePage = lazyPage(() => import("@/features/investigations/NewCasePage"), "NewCasePage");
const CaseDetailPage = lazyPage(() => import("@/features/investigations/CaseDetailPage"), "CaseDetailPage");
const WalletExplorerPage = lazyPage(() => import("@/features/wallets/WalletExplorerPage"), "WalletExplorerPage");
const WalletDetailPage = lazyPage(() => import("@/features/wallets/WalletDetailPage"), "WalletDetailPage");
const TransactionsPage = lazyPage(() => import("@/features/transactions/TransactionsPage"), "TransactionsPage");
const GraphPage = lazyPage(() => import("@/features/graph/GraphPage"), "GraphPage");
const VaspPage = lazyPage(() => import("@/features/vasp/VaspPage"), "VaspPage");
const SahyogPage = lazyPage(() => import("@/features/sahyog/SahyogPage"), "SahyogPage");
const EvidencePage = lazyPage(() => import("@/features/evidence/EvidencePage"), "EvidencePage");
const RiskPage = lazyPage(() => import("@/features/risk/RiskPage"), "RiskPage");
const ReportsPage = lazyPage(() => import("@/features/reports/ReportsPage"), "ReportsPage");
const AuditPage = lazyPage(() => import("@/features/audit/AuditPage"), "AuditPage");
const UsersPage = lazyPage(() => import("@/features/admin/UsersPage"), "UsersPage");
const RolesPage = lazyPage(() => import("@/features/admin/RolesPage"), "RolesPage");
const SettingsPage = lazyPage(() => import("@/features/admin/SettingsPage"), "SettingsPage");
const NotFoundPage = lazyPage(() => import("@/features/NotFoundPage"), "NotFoundPage");

function RouteSuspense({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<RouteFallback />}>{children}</Suspense>;
}

/**
 * Route-level RBAC. Mirrors the demo permission grid; the backend remains the
 * final authorization authority once auth is implemented server-side.
 */
function PermissionBoundary({ permission, children }: { permission?: Permission; children: React.ReactNode }) {
  const { can } = useAuth();
  if (permission && !can(permission)) {
    return (
      <div className="page">
        <UnauthorizedState />
      </div>
    );
  }
  return <>{children}</>;
}

function RouteFallback() {
  return (
    <div className="page" role="status" aria-label="Loading route">
      <SkeletonTitle />
      <SkeletonBlock rows={6} />
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <AuthProvider>
          <DataSourceProvider>
            <RouteSuspense>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<ProtectedRoute />}>
                  <Route element={<AppShell />}>
                    <Route index element={<Navigate to="/dashboard" replace />} />
                    <Route path="dashboard" element={<DashboardPage />} />
                    <Route path="search" element={<PermissionBoundary permission="search.read"><SearchPage /></PermissionBoundary>} />
                    <Route path="investigations" element={<PermissionBoundary permission="investigation.read"><CasesPage /></PermissionBoundary>} />
                    <Route path="cases/new" element={<PermissionBoundary permission="investigation.create"><NewCasePage /></PermissionBoundary>} />
                    <Route path="cases/:id" element={<PermissionBoundary permission="investigation.read"><CaseDetailPage /></PermissionBoundary>} />
                    <Route path="wallets" element={<PermissionBoundary permission="wallet.read"><WalletExplorerPage /></PermissionBoundary>} />
                    <Route path="wallets/:address" element={<PermissionBoundary permission="wallet.read"><WalletDetailPage /></PermissionBoundary>} />
                    <Route path="transactions" element={<PermissionBoundary permission="wallet.read"><TransactionsPage /></PermissionBoundary>} />
                    <Route path="graph" element={<PermissionBoundary permission="graph.read"><GraphPage /></PermissionBoundary>} />
                    <Route path="vasp" element={<PermissionBoundary permission="attribution.read"><VaspPage /></PermissionBoundary>} />
                    <Route path="sahyog" element={<PermissionBoundary permission="wallet.analyze"><SahyogPage /></PermissionBoundary>} />
                    <Route path="evidence" element={<PermissionBoundary permission="evidence.read"><EvidencePage /></PermissionBoundary>} />
                    <Route path="risk" element={<PermissionBoundary permission="risk.read"><RiskPage /></PermissionBoundary>} />
                    <Route path="reports" element={<PermissionBoundary permission="report.export"><ReportsPage /></PermissionBoundary>} />
                    <Route path="audit" element={<PermissionBoundary permission="audit.read"><AuditPage /></PermissionBoundary>} />
                    <Route path="admin/users" element={<PermissionBoundary permission="user.manage"><UsersPage /></PermissionBoundary>} />
                    <Route path="admin/roles" element={<PermissionBoundary permission="user.manage"><RolesPage /></PermissionBoundary>} />
                    <Route path="admin/settings" element={<PermissionBoundary permission="user.manage"><SettingsPage /></PermissionBoundary>} />
                    <Route path="*" element={<NotFoundPage />} />
                  </Route>
                </Route>
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </RouteSuspense>
          </DataSourceProvider>
        </AuthProvider>
      </BrowserRouter>
    </ToastProvider>
  );
}