import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/auth/AuthContext";
import { ToastProvider } from "@/components/ui";
import { LoginPage } from "@/features/auth/LoginPage";
import { UsersPage } from "@/features/admin/UsersPage";
import { users } from "@/api/users";
import { auth, backendUserToAppUser, type BackendUserOut } from "@/api/auth";
import { clearToken, getToken, saveToken } from "@/auth/tokenStore";

/**
 * Live auth + user-management flows.
 *
 * The shared setup stubs `fetch` to report the backend as unreachable (503),
 * which drives the demo fallback. Individual tests here substitute success /
 * specific-error responses to exercise the real wiring: token persistence,
 * list/create/update/disable against /api/v1/admin/users, and the
 * permission-gated Users page.
 */

function okJson(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(payload),
  } as unknown as Response;
}

function errorJson(status: number, statusText: string, detail: string): Response {
  return {
    ok: false,
    status,
    statusText,
    text: async () => JSON.stringify({ detail }),
  } as unknown as Response;
}

const backendUser: BackendUserOut = {
  id: "u-1",
  username: "inspector",
  display_name: "Priya Sharma",
  email: "priya@example.gov",
  role: "investigator",
  title: "Officer",
  is_active: true,
  is_demo: false,
  last_active_at: "2026-09-10T04:00:00Z",
};

describe("auth mapping", () => {
  it("maps a backend user onto the app user shape", () => {
    const u = backendUserToAppUser(backendUser);
    expect(u.id).toBe("u-1");
    expect(u.username).toBe("inspector");
    expect(u.name).toBe("Priya Sharma");
    expect(u.role).toBe("investigator");
    expect(u.title).toBe("Officer");
    expect(u.lastActive).toBeTruthy();
  });

  it("falls back to username when display_name is missing", () => {
    const u = backendUserToAppUser({ ...backendUser, display_name: "" });
    expect(u.name).toBe("inspector");
  });

  it("maps an unknown backend role to read_only instead of crashing", () => {
    const u = backendUserToAppUser({ ...backendUser, role: "owner" });
    expect(u.role).toBe("read_only");
  });
});

describe("live login flow", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("stores the opaque bearer token and returns the mapped user", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        okJson({
          access_token: "signed-token-abc",
          token_type: "bearer",
          expires_in: 7200,
          user: backendUser,
        }),
      ),
    );

    const res = await auth.login("inspector", "correct-password");
    expect(res.ok).toBe(true);
    expect(res.user?.username).toBe("inspector");
    expect(getToken()).toBe("signed-token-abc");
  });

  it("does not persist a token on backend rejection", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => errorJson(401, "Unauthorized", "Bad username or password")));

    const res = await auth.login("inspector", "wrong-password");
    expect(res.ok).toBe(false);
    expect(res.status).toBe(401);
    expect(getToken()).toBeNull();
  });

  it("logout discards the token even when the backend is unreachable", async () => {
    saveToken("signed-token-abc", 7200);
    await auth.logout();
    expect(getToken()).toBeNull();
  });
});

describe("user-management API flows", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    clearToken();
  });

  it("degrades to an empty list when the backend is unreachable", async () => {
    const list = await users.list();
    expect(list).toEqual([]);
  });

  it("maps a live user list onto AppUser rows", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        okJson({
          users: [backendUser, { ...backendUser, id: "u-2", username: "analyst", role: "analyst" }],
          source: "db",
        }),
      ),
    );

    const list = await users.list();
    expect(list).toHaveLength(2);
    expect(list[0].id).toBe("u-1");
    expect(list[1].role).toBe("analyst");
  });

  it("PATCHes the update path with the submitted role", async () => {
    const fetchMock = vi.fn(async () => okJson({ ...backendUser, role: "reviewer" }));
    vi.stubGlobal("fetch", fetchMock);

    await users.update("u-1", { role: "reviewer" });

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/admin/users/u-1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ role: "reviewer" });
  });

  it("POSTs create with the full payload", async () => {
    const fetchMock = vi.fn(async () => okJson(backendUser));
    vi.stubGlobal("fetch", fetchMock);

    await users.create({
      username: "inspector",
      display_name: "Priya Sharma",
      email: "priya@example.gov",
      role: "investigator",
      title: "Officer",
      password: "temp-password",
    });

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/admin/users");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string);
    expect(body.role).toBe("investigator");
    expect(body.password).toBe("temp-password");
  });

  it("DELETE disables a user account", async () => {
    const fetchMock = vi.fn(async () => okJson({ ...backendUser, is_active: false }));
    vi.stubGlobal("fetch", fetchMock);

    await users.disable("u-1");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/api/v1/admin/users/u-1");
    expect(init.method).toBe("DELETE");
  });

  it("surfaces a user-safe error when create is forbidden", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => errorJson(403, "Forbidden", "not permitted")));

    await expect(
      users.create({
        username: "inspector",
        display_name: "Priya Sharma",
        role: "investigator",
        password: "temp-password",
      }),
    ).rejects.toThrow(/do not have permission/i);
  });
});

describe("Users page RBAC", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  async function login(src: "admin" | "reviewer") {
    const user = userEvent.setup();
    const username = src === "admin" ? "admin" : "reviewer";
    const input = screen.getByLabelText(/Username/i);
    await user.clear(input);
    await user.type(input, username);
    const pass = screen.getByLabelText(/Password/i);
    await user.clear(pass);
    await user.type(pass, "cryptotrace-demo");
    await user.click(screen.getByRole("button", { name: /Sign in/i }));
  }

  function renderUsers() {
    return render(
      <MemoryRouter initialEntries={["/login"]}>
        <ToastProvider>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<UsersPage />} />
            </Routes>
          </AuthProvider>
        </ToastProvider>
      </MemoryRouter>,
    );
  }

  it("renders the user directory for an admin", async () => {
    renderUsers();
    await login("admin");

    expect(await screen.findByRole("heading", { name: "Users" })).toBeInTheDocument();
    expect(screen.getByText("Arya Verma")).toBeInTheDocument();
    expect(screen.getAllByRole("row").length).toBeGreaterThan(1);
  });

  it("blocks a role without user.manage", async () => {
    renderUsers();
    await login("reviewer");

    expect(await screen.findByText(/does not permit managing users/i)).toBeInTheDocument();
    expect(screen.queryByText("Administrator")).not.toBeInTheDocument();
  });
});
