import type { AppUser, Role } from "@/api/types";

/**
 * DEMO ACCOUNTS ONLY.
 *
 * Authentication is NOT implemented in the backend yet. These credentials are
 * purely for exercising the frontend RBAC/session UI and are never used to
 * authorize anything on the server. The backend remains the final
 * authorization authority once real auth exists.
 */
export interface DemoCredentials {
  username: string;
  password: string;
  userId: string;
}

export const demoUsers: AppUser[] = [
  {
    id: "u-admin",
    username: "admin",
    name: "Arya Verma",
    role: "admin",
    title: "Platform Administrator",
    email: "arya.admin@cryptotrace.local",
    lastActive: new Date().toISOString(),
    isActive: true,
  },
  {
    id: "u-sinv",
    username: "senior_investigator",
    name: "Rohan Iyer",
    role: "senior_investigator",
    title: "Senior Investigator",
    email: "rohan.senior@cryptotrace.local",
    lastActive: new Date().toISOString(),
    isActive: true,
  },
  {
    id: "u-inv",
    username: "investigator",
    name: "Aarav Kapoor",
    role: "investigator",
    title: "Investigator",
    email: "aarav.inv@cryptotrace.local",
    lastActive: new Date().toISOString(),
    isActive: true,
  },
  {
    id: "u-analyst",
    username: "analyst",
    name: "Meera Nair",
    role: "analyst",
    title: "Blockchain Intelligence Analyst",
    email: "meera.analyst@cryptotrace.local",
    lastActive: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
    isActive: true,
  },
  {
    id: "u-reviewer",
    username: "reviewer",
    name: "Kabir Shah",
    role: "reviewer",
    title: "Case Reviewer",
    email: "kabir.review@cryptotrace.local",
    lastActive: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
    isActive: true,
  },
  {
    id: "u-read",
    username: "readonly",
    name: "Nisha Rao",
    role: "read_only",
    title: "Read-Only Analyst",
    email: "nisha.read@cryptotrace.local",
    lastActive: new Date(Date.now() - 1000 * 60 * 60 * 72).toISOString(),
    isActive: false,
  },
];

export const demoCredentials: DemoCredentials[] = [
  { username: "admin", password: "cryptotrace-demo", userId: "u-admin" },
  { username: "senior_investigator", password: "cryptotrace-demo", userId: "u-sinv" },
  { username: "investigator", password: "cryptotrace-demo", userId: "u-inv" },
  { username: "analyst", password: "cryptotrace-demo", userId: "u-analyst" },
  { username: "reviewer", password: "cryptotrace-demo", userId: "u-reviewer" },
  { username: "readonly", password: "cryptotrace-demo", userId: "u-read" },
];

/** Permission grid for the DEMO RBAC. Backend must re-enforce these. */
export const ROLE_PERMISSIONS: Record<Role, readonly string[]> = {
  admin: [
    "search.read",
    "investigation.read",
    "investigation.create",
    "investigation.update",
    "wallet.read",
    "wallet.analyze",
    "graph.read",
    "attribution.read",
    "evidence.read",
    "evidence.create",
    "evidence.delete",
    "risk.read",
    "report.create",
    "report.export",
    "audit.read",
    "user.manage",
    "settings.manage",
  ],
  senior_investigator: [
    "search.read",
    "investigation.read",
    "investigation.create",
    "investigation.update",
    "wallet.read",
    "wallet.analyze",
    "graph.read",
    "attribution.read",
    "evidence.read",
    "evidence.create",
    "evidence.delete",
    "risk.read",
    "report.create",
    "report.export",
  ],
  investigator: [
    "search.read",
    "investigation.read",
    "investigation.create",
    "investigation.update",
    "wallet.read",
    "wallet.analyze",
    "graph.read",
    "attribution.read",
    "evidence.read",
    "evidence.create",
    "risk.read",
    "report.create",
    "report.export",
  ],
  analyst: [
    "search.read",
    "investigation.read",
    "investigation.create",
    "investigation.update",
    "wallet.read",
    "wallet.analyze",
    "graph.read",
    "attribution.read",
    "evidence.read",
    "evidence.create",
    "risk.read",
    "report.create",
  ],
  reviewer: [
    "search.read",
    "investigation.read",
    "wallet.read",
    "graph.read",
    "attribution.read",
    "evidence.read",
    "risk.read",
    "report.create",
    "report.export",
  ],
  read_only: ["search.read", "investigation.read", "wallet.read", "graph.read", "attribution.read", "evidence.read", "risk.read"],
};

export function allDemoRoles(): Role[] {
  return ["admin", "senior_investigator", "investigator", "analyst", "reviewer", "read_only"];
}
