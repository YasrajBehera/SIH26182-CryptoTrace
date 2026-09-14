import { useMemo, useState } from "react";
import { PageHeader, Button, Card, DemoBadge, Input, Select, Badge } from "@/components/ui";
import { AddIcon } from "@/components/icons";
import { useAuth } from "@/auth/AuthContext";
import { demoUsers } from "@/mock/users";
import { useToast } from "@/components/ui";
import type { AppUser, Role } from "@/api/types";

const ROLE_LABEL: Record<Role, string> = {
  admin: "Administrator",
  senior_investigator: "Senior Investigator",
  investigator: "Investigator",
  analyst: "Analyst",
  reviewer: "Reviewer",
  read_only: "Read-only",
};

export function UsersPage() {
  const { can, role } = useAuth();
  const { push } = useToast();
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");

  const filtered = useMemo(
    () =>
      demoUsers.filter((u) => {
        if (roleFilter !== "all" && u.role !== roleFilter) return false;
        if (q) {
          const needle = q.toLowerCase();
          if (!`${u.name} ${u.email} ${u.id} ${u.title}`.toLowerCase().includes(needle)) return false;
        }
        return true;
      }),
    [q, roleFilter],
  );

  if (!can("user.manage")) {
    return (
      <div className="page">
        <PageHeader title="Users" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>
            Your role ({role}) does not permit managing users. User management is administered server-side; admin
            access is required to provision or modify accounts.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Users"
        subtitle="Directory of analyst accounts provisioned by the backend demo seed."
        crumbs={[{ label: "Administration" }, { label: "Users" }]}
        actions={
          <>
            <DemoBadge />
            <Button
              variant="primary"
              leading={<AddIcon />}
              onClick={() => push({ kind: "info", title: "User creation is not wired in this build", description: "Provision accounts server-side; no user was created." })}
            >
              Add user
            </Button>
          </>
        }
      />

      <Card>
        <div className="table-toolbar">
          <Input style={{ maxWidth: 240 }} placeholder="Search name, email…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search users" />
          <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label="Filter by role" style={{ maxWidth: 180 }}>
            <option value="all">All roles</option>
            {(Object.keys(ROLE_LABEL) as Role[]).map((r) => (
              <option key={r} value={r}>{ROLE_LABEL[r]}</option>
            ))}
          </Select>
          <span className="spacer" />
          <Badge className="status-draft">{filtered.length} users</Badge>
        </div>

        {filtered.length ? (
          <table className="data-table" aria-label="Users">
            <thead>
              <tr>
                <th>Name</th>
                <th>Title</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last active</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u: AppUser) => (
                <tr key={u.id}>
                  <td>
                    <strong>{u.name}</strong>
                    <span style={{ display: "block", fontSize: "var(--text-xs)", color: "var(--text-faint)" }}>{u.id}</span>
                  </td>
                  <td>{u.title}</td>
                  <td>{u.email}</td>
                  <td><Badge className={u.role === "admin" ? "status-investigating" : "status-open"}>{ROLE_LABEL[u.role]}</Badge></td>
                  <td>
                    <Badge className={u.isActive ? "status-success" : "status-draft"}>{u.isActive ? "Active" : "Inactive"}</Badge>
                  </td>
                  <td>{u.lastActive ? new Date(u.lastActive).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Card>
            <p style={{ color: "var(--text-faint)", textAlign: "center", padding: "var(--space-6)" }}>No users match the current filters.</p>
          </Card>
        )}
      </Card>
    </div>
  );
}