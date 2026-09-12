import { client } from "./client";
import { backendUserToAppUser, type BackendUserOut } from "./auth";
import type { AppUser, Role } from "./types";

/**
 * Admin user management (live mode):
 *   GET    /api/v1/admin/users            -> list
 *   POST   /api/v1/admin/users            -> create
 *   PATCH  /api/v1/admin/users/{id}       -> update
 *   DELETE /api/v1/admin/users/{id}       -> disable
 */
export interface UserListResponse {
  users: BackendUserOut[];
  source: string;
}

export interface CreateUserInput {
  username: string;
  display_name: string;
  email?: string;
  role: Role;
  title?: string;
  password: string;
}

export interface UpdateUserInput {
  display_name?: string;
  email?: string;
  role?: Role;
  title?: string;
  is_active?: boolean;
}

export const users = {
  async list(): Promise<AppUser[]> {
    try {
      const res = await client.get<UserListResponse>("/api/v1/admin/users");
      return (res.users ?? []).map(backendUserToAppUser);
    } catch {
      return [];
    }
  },

  async create(input: CreateUserInput): Promise<AppUser> {
    const res = await client.post<BackendUserOut>("/api/v1/admin/users", input);
    return backendUserToAppUser(res);
  },

  async update(id: string, input: UpdateUserInput): Promise<AppUser> {
    const res = await client.patch<BackendUserOut>(`/api/v1/admin/users/${encodeURIComponent(id)}`, input);
    return backendUserToAppUser(res);
  },

  async disable(id: string): Promise<AppUser> {
    const res = await client.del<BackendUserOut>(`/api/v1/admin/users/${encodeURIComponent(id)}`);
    return backendUserToAppUser(res);
  },
};