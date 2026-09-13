import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "@/components/ui";
import { AuthProvider } from "@/auth/AuthContext";
import { DataSourceProvider } from "@/app/DataSourceContext";
import { DashboardPage } from "@/features/dashboard/DashboardPage";

function renderDashboard() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <ToastProvider>
        <AuthProvider>
          <DataSourceProvider>
            <DashboardPage />
          </DataSourceProvider>
        </AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("Investigator dashboard", () => {
  it("renders the full workstation at /dashboard", async () => {
    renderDashboard();

    expect(await screen.findByText(/Investigation Overview/i)).toBeInTheDocument();

    // Header actions
    expect(screen.getByRole("heading", { name: /Investigation Overview/i })).toBeInTheDocument();

    // KPI grid (metric label also appears as a card title below)
    expect(screen.getAllByText("Active Investigations").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Wallets Analyzed")).toBeInTheDocument();
    expect(screen.getByText("High-Risk Wallets")).toBeInTheDocument();
    // "VASP Candidates" also appears as a step in the investigation workflow strip
    expect(screen.getAllByText("VASP Candidates").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Evidence Items")).toBeInTheDocument();
    expect(screen.getByText("Open Alerts")).toBeInTheDocument();

    // System status
    expect(screen.getByText("System Status")).toBeInTheDocument();

    // Risk overview
    expect(screen.getByText("Risk Intelligence")).toBeInTheDocument();

    // Investigation control bar + table
    expect(screen.getAllByText("Active Investigations").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("group", { name: /Investigation filters/i })).toBeInTheDocument();

    // Evidence + VASP tables
    expect(screen.getByText(/VASP Intelligence/i)).toBeInTheDocument();
  });

  it("shows honest per-engine status instead of fabricated availability", async () => {
    renderDashboard();
    await screen.findByText(/Investigation Overview/i);

    const unavailable = screen.getAllByText("Not available");
    expect(unavailable.length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Not connected").length).toBeGreaterThanOrEqual(1);
    // No live session in the test harness — the status card must tell the user
    // to sign in and must never claim a fabricated "Connected" state.
    expect(screen.getByText("Sign in to connect")).toBeInTheDocument();
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
  });

  it("does not claim verified ownership for VASP candidates", async () => {
    renderDashboard();
    await screen.findByText(/Investigation Overview/i);

    expect(screen.getByText(/Potential associations — not verified ownership/i)).toBeInTheDocument();
    expect(screen.queryByText(/owns this wallet/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/confirmed owner/i)).not.toBeInTheDocument();
  });
});