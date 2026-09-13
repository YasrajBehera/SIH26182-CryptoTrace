import { PageHeader, Button, Card, DemoBadge, Badge } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/ui";
import { ROLE_PERMISSIONS, allDemoRoles } from "@/mock/users";
import type { Role, Permission } from "@/api/types";

const ROLE_LABEL: Record<Role, string> = {
  admin: "Administrator",
  senior_investigator: "Senior Investigator",
  investigator: "Investigator",
  analyst: "Analyst",
  reviewer: "Reviewer",
  read_only: "Read-only",
};

const PERMISSION_LABEL: Record<Permission, string> = {
  "search.read": "Use global search",
  "investigation.read": "View investigations",
  "investigation.create": "Create investigations",
  "investigation.update": "Update investigations",
  "wallet.read": "View wallets",
  "wallet.analyze": "Analyze wallets",
  "graph.read": "View transaction graph",
  "attribution.read": "View VASP attribution",
  "evidence.read": "View evidence",
  "evidence.create": "Attach evidence",
  "evidence.delete": "Delete evidence",
  "risk.read": "View risk analysis",
  "report.create": "Create reports",
  "report.export": "Export reports",
  "audit.read": "View audit log",
  "user.manage": "Manage users",
  "settings.manage": "Manage settings",
};

export function RolesPage() {
  const { role, can } = useAuth();
  const { push } = useToast();

  if (!can("user.manage")) {
    return (
      <div className="page">
        <PageHeader title="Roles & Permissions" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>
            Your role ({role}) does not permit viewing role configuration. Role management ships with backend auth.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Roles & Permissions"
        subtitle="Demo RBAC matrix. The backend MUST re-enforce these same rules once real authentication exists."
        crumbs={[{ label: "Administration" }, { label: "Roles & Permissions" }]}
        actions={
          <>
            <DemoBadge />
            <Button
              variant="ghost"
              onClick={() => push({ kind: "info", title: "Role editing (demo)", description: "Persisting role changes requires backend identity management." })}
            >
              Edit roles
            </Button>
          </>
        }
      />

      <div className="risk-rule rr-low" role="note">
        <strong>Security note:</strong> role checks in the UI are convenience guards only. Authorization decisions on
        the backend are out of scope of this frontend release and must be enforced server-side.
      </div>

      {allDemoRoles().map((r: Role) => (
        <Card
          key={r}
          title={
            <span className="row" style={{ gap: 8 }}>
              {ROLE_LABEL[r]}
              <Badge className="status-open">{r}</Badge>
            </span>
          }
          subtitle={`${ROLE_PERMISSIONS[r].length} permissions`}
        >
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            {ROLE_PERMISSIONS[r].map((p) => (
              <Badge key={p} className="status-success" title={p}>
                {PERMISSION_LABEL[p as Permission] ?? p}
              </Badge>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}