import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { LoginPage } from "@/features/auth/LoginPage";
import { ToastProvider } from "@/components/ui";

function AuthProbe() {
  const { isAuthenticated, can, user } = useAuth();
  return (
    <div>
      <span data-testid="authed">{String(isAuthenticated)}</span>
      <span data-testid="name">{user?.name ?? "none"}</span>
      <span data-testid="role">{user?.role ?? "none"}</span>
      <span data-testid="can-create">{String(can("investigation.create"))}</span>
      <span data-testid="can-manage">{String(can("user.manage"))}</span>
      <span data-testid="can-read">{String(can("investigation.read"))}</span>
    </div>
  );
}

function renderAt(path: string, routes: React.ReactNode) {
  return render(
    <ToastProvider>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>{routes}</MemoryRouter>
      </AuthProvider>
    </ToastProvider>,
  );
}

describe("demo auth + RBAC", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("logs in with admin credentials, navigates, and grants the permission matrix", async () => {
    const user = userEvent.setup();
    renderAt("/login", (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<AuthProbe />} />
      </Routes>
    ));

    const input = screen.getByLabelText(/Username/i);
    await user.clear(input);
    await user.type(input, "admin");
    const pass = screen.getByLabelText(/Password/i);
    await user.clear(pass);
    await user.type(pass, "cryptotrace-demo");
    await user.click(screen.getByRole("button", { name: /Sign in/i }));

    expect(await screen.findByTestId("authed")).toHaveTextContent("true");
    expect(screen.getByTestId("name")).toHaveTextContent("Arya Verma");
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(screen.getByTestId("can-create")).toHaveTextContent("true");
    expect(screen.getByTestId("can-manage")).toHaveTextContent("true");
  });

  it("logs in as reviewer without destructive permissions", async () => {
    const user = userEvent.setup();
    renderAt("/login", (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<AuthProbe />} />
      </Routes>
    ));

    const input = screen.getByLabelText(/Username/i);
    await user.clear(input);
    await user.type(input, "reviewer");
    const pass = screen.getByLabelText(/Password/i);
    await user.clear(pass);
    await user.type(pass, "cryptotrace-demo");
    await user.click(screen.getByRole("button", { name: /Sign in/i }));

    expect(await screen.findByTestId("authed")).toHaveTextContent("true");
    expect(screen.getByTestId("can-create")).toHaveTextContent("false");
    expect(screen.getByTestId("can-manage")).toHaveTextContent("false");
    expect(screen.getByTestId("can-read")).toHaveTextContent("true");
  });

  it("rejects invalid demo credentials with a safe message", async () => {
    const user = userEvent.setup();
    renderAt("/login", (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    ));

    const input = screen.getByLabelText(/Username/i);
    await user.clear(input);
    await user.type(input, "admin");
    const pass = screen.getByLabelText(/Password/i);
    await user.clear(pass);
    await user.type(pass, "wrong-password");
    await user.click(screen.getByRole("button", { name: /Sign in/i }));

    expect(await screen.findByText(/Invalid demo credentials/i)).toBeInTheDocument();
  });

  it("resolves can() to false for an unauthenticated session", () => {
    renderAt("/", (
      <Routes>
        <Route path="/" element={<AuthProbe />} />
      </Routes>
    ));
    expect(screen.getByTestId("authed")).toHaveTextContent("false");
    expect(screen.getByTestId("can-create")).toHaveTextContent("false");
    expect(screen.getByTestId("can-manage")).toHaveTextContent("false");
  });

  it("ProtectedRoute redirects anonymous users to /login", () => {
    renderAt("/", (
      <Routes>
        <Route path="/login" element={<div data-testid="login-view">Login screen</div>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<div data-testid="home-view">Home</div>} />
        </Route>
      </Routes>
    ));
    expect(screen.getByTestId("login-view")).toBeInTheDocument();
    expect(screen.queryByTestId("home-view")).not.toBeInTheDocument();
  });

  it("lets authenticated users through ProtectedRoute", async () => {
    const user = userEvent.setup();
    renderAt("/login", (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<div data-testid="home-view">Home</div>} />
        </Route>
      </Routes>
    ));

    const input = screen.getByLabelText(/Username/i);
    await user.clear(input);
    await user.type(input, "admin");
    const pass = screen.getByLabelText(/Password/i);
    await user.clear(pass);
    await user.type(pass, "cryptotrace-demo");
    await user.click(screen.getByRole("button", { name: /Sign in/i }));

    expect(await screen.findByTestId("home-view")).toBeInTheDocument();
  });
});