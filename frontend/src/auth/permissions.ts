import type { Permission, Role } from "@/api/types";
import { ROLE_PERMISSIONS } from "@/mock/users";

/**
 * Permission helper.
 *
 * SECURITY MODEL: the backend is the final authorization authority. This
 * helper only guards the UI (hide/disable actions). It must never be treated
 * as a real access-control boundary.
 */
export function canRole(role: Role | null, permission: Permission): boolean {
  if (!role) return false;
  return ROLE_PERMISSIONS[role].includes(permission);
}

export function canAnyRole(role: Role | null, permissions: Permission[]): boolean {
  if (!role) return false;
  return permissions.some((p) => ROLE_PERMISSIONS[role].includes(p));
}