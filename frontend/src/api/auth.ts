import { client, ApiError } from "./client";
import { clearToken, saveToken } from "@/auth/tokenStore";
import type { AppUser, Role } from "./types";

/**
 * Backend auth contract (live mode):
 *   POST /api/v1/auth/login          -> { access_token, expires_in, user }
 *   POST /api/v1/auth/logout
 *   GET  /api/v1/auth/me             -> { id, username, display_name, ... }
 *   POST /api/v1/auth/change-password
 */

export interface BackendUserOut {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: string;
  title: string;
  is_active: boolean;
  is_demo: boolean;
  last_active_at: string | null;
  created_at?: string | null;
}

export interface TokenResponsePayload {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: BackendUserOut;
}

export interface LoginResult {
  ok: boolean;
  token?: string;
  expiresIn?: number;
  user?: AppUser;
  error?: string;
  status?: number;
}

const ROLE_FALLBACK: Role = "read_only";

function toRole(role: string): Role {
  const known: Role[] = ["admin", "senior_investigator", "investigator", "analyst", "reviewer", "read_only"];
  return (known as string[]).includes(role) ? (role as Role) : ROLE_FALLBACK;
}

export function backendUserToAppUser(u: BackendUserOut): AppUser {
  return {
    id: u.id,
    username: u.username,
    name: u.display_name || u.username,
    role: toRole(u.role),
    title: u.title,
    email: u.email,
    lastActive: u.last_active_at ?? undefined,
    isActive: u.is_active,
  };
}

export const auth = {
  /** Attempt a real backend login. Callers decide whether to fall back to demo. */
  async login(username: string, password: string): Promise<LoginResult> {
    try {
      const res = await client.post<TokenResponsePayload>("/api/v1/auth/login", {
        username,
        password,
      });
      if (!res.access_token) {
        return { ok: false, error: "The server did not return a session token." };
      }
      saveToken(res.access_token, res.expires_in > 0 ? res.expires_in : 7200);
      return {
        ok: true,
        token: res.access_token,
        expiresIn: res.expires_in,
        user: backendUserToAppUser(res.user),
      };
    } catch (err) {
      if (err instanceof ApiError) {
        return { ok: false, error: err.message, status: err.status };
      }
      return { ok: false, error: String(err) };
    }
  },

  async logout(): Promise<void> {
    try {
      await client.post<{ detail: string; ok: boolean }>("/api/v1/auth/logout");
    } catch {
      // Stateless logout — discarding the token locally is sufficient.
    } finally {
      clearToken();
    }
  },

  async me(): Promise<AppUser | null> {
    try {
      const res = await client.get<BackendUserOut>("/api/v1/auth/me");
      return backendUserToAppUser(res);
    } catch {
      return null;
    }
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<{ ok: boolean; error?: string }> {
    try {
      await client.post("/api/v1/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      return { ok: true };
    } catch (err) {
      if (err instanceof ApiError) return { ok: false, error: err.message };
      return { ok: false, error: "Password change failed." };
    }
  },
};

export const rolesApi = {
  async list(): Promise<{ role: string; permissions: string[] }[]> {
    const res = await client.get<{ role: string; permissions: string[] }[]>("/api/v1/admin/users/roles");
    return res ?? [];
  },
};