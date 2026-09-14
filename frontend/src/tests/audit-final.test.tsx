import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import type { ReactNode } from "react";
import { ToastProvider } from "@/components/ui";

/**
 * Final-system audit tests.
 *
 * These assert the product's "UI truth": live components must never show
 * stale "Member 2 / engine ships" copy, must never render synthetic matter in
 * LIVE mode, must use the investigation's persisted data where it exists, and
 * must not fire repeated/looping requests for a single user action.
 */

vi.setConfig({ testTimeout: 20000 });

// ---- shared fixtures (real-looking, non-synthetic addresses) ----
const WALLET = "0x098b716b8aaf21512996dc57eb0615e2383e2f96";
const PEER = "0x2222aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const walletId = `ethereum:${WALLET}`;
const peerId = `ethereum:${PEER}`;

const EMPTY_PATH = {
  nodes: [] as never[],
  edges: [] as never[],
  metrics: {
    pathLength: 0,
    transactionCount: 0,
    totalValue: "0",
    asset: "ETH",
    timeElapsed: "—" as string | undefined,
    confidence: null as number | null,
  },
};

// ---- test seam: flip between live and demo per test ----
let mockLive = false;
beforeEach(() => {
  mockLive = false;
});

vi.mock("@/app/DataSourceContext", () => ({
  DataSourceProvider: ({ children }: { children: ReactNode }) => children,
  useDataSource: () => ({
    mode: mockLive ? "live" : "demo",
    backendReachable: mockLive,
    sessionActive: mockLive,
    checking: false,
    setMode: vi.fn(),
    isDemo: !mockLive,
  }),
}));

vi.mock("@/auth/AuthContext", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => children,
  useAuth: () => ({
    user: { id: "u-audit", name: "Audit Admin", username: "audit", role: "admin", title: "Admin", email: "audit@cryptotrace.local" },
    role: "admin",
    username: "audit",
    isAuthenticated: true,
    isDemoAuth: false,
    login: vi.fn(),
    logout: vi.fn(),
    can: () => true,
    idleSecondsRemaining: 0,
    sessionExpired: false,
  }),
}));

const queryMock = vi.fn();
const healthMock = vi.fn();
const pathMock = vi.fn();
vi.mock("@/api/graph", () => ({
  graph: {
    health: (...args: unknown[]) => healthMock(...args),
    query: (...args: unknown[]) => queryMock(...args),
    path: (...args: unknown[]) => pathMock(...args),
  },
  toWalletId: (address: string) => `ethereum:${address}`,
}));

vi.mock("@/api/investigations", () => ({
  investigations: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn().mockResolvedValue(null),
    context: vi.fn().mockResolvedValue(null),
    analyze: vi.fn(),
    create: vi.fn(),
    notes: vi.fn().mockResolvedValue([]),
    addNote: vi.fn(),
    timeline: vi.fn().mockResolvedValue([]),
  },
  activity: { feed: vi.fn().mockResolvedValue([]) },
  getLastAnalysis: () => null,
  setLastAnalysis: vi.fn(),
  networkLabel: (n: string) => (n === "eth" || n === "ethereum" ? "Ethereum" : n),
  mapPersistedCandidatesToView: () => [],
  mapBackendInvestigationToView: (b: Record<string, unknown>) => b,
}));

vi.mock("@/api/assistant", () => ({
  assistant: {
    quickActions: vi.fn().mockResolvedValue([]),
    query: vi.fn().mockResolvedValue({
      request_id: "asr-audit-1",
      intent: "suspicious_transactions",
      title: "Suspicious activity review",
      sections: [
        { heading: "Review", body: "Grounded review body", bullets: ["Counterparties appearing in 3+ transactions (review)"], actions: [] },
      ],
      evidence_ids: [],
      transaction_hashes: [],
      warnings: [],
      disclaimer: "Attribution is a transactional association, not ownership proof.",
      data_source: "live",
      human_review_required: true,
      suggested_actions: [],
      referral_draft: null,
    }),
  },
}));

vi.mock("@/api/attribution", () => ({
  attribution: {
    candidates: vi.fn().mockResolvedValue([]),
    get: vi.fn().mockResolvedValue(null),
    intelligence: vi.fn().mockResolvedValue(null),
    vaspNames: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("@/api/evidence", () => ({
  evidence: {
    list: vi.fn().mockResolvedValue([]),
    provenance: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("@/api/system", () => ({
  system: {
    status: vi.fn().mockResolvedValue({
      backend: true,
      auth: true,
      postgres: false,
      blockchain: true,
      neo4j: true,
      graph: true,
      vasp: true,
      report: true,
      sahyog: true,
      sahyog_production: false,
    }),
  },
}));

const walletTransfersMock = vi.fn();
const walletSummaryMock = vi.fn();
vi.mock("@/api/wallets", () => ({
  wallets: {
    health: vi.fn().mockResolvedValue({ ok: true }),
    getSummary: (...args: unknown[]) => walletSummaryMock(...args),
    getTransfers: (...args: unknown[]) => walletTransfersMock(...args),
  },
}));

// ---- helpers ----
function graphFixture(address: string) {
  return {
    nodes: [
      { id: `ethereum:${address}`, address, type: "wallet" as const, risk: "high" as const, label: address, metadata: { asset: "ETH", txCount: 5 } },
      { id: peerId, address: PEER, type: "vasp" as const, risk: "unknown" as const, label: PEER, metadata: {} },
    ],
    edges: [
      {
        id: "e0",
        source: `ethereum:${address}`,
        target: peerId,
        transactionHash: `0x${"ee".repeat(32)}`,
        asset: "ETH",
        amount: "10.5",
        timestamp: "2026-01-01T00:00:00Z",
        blockNumber: 1,
      },
    ],
  };
}

let transferSeq = 0;
function makeTransfer(overrides: Partial<import("@/api/types").BlockchainTransfer> = {}): import("@/api/types").BlockchainTransfer {
  transferSeq += 1;
  return {
    transaction_hash: `0x${transferSeq.toString(16).padStart(64, "0")}`,
    block_number: 19345310,
    block_timestamp: "2026-01-02T10:00:00Z",
    from_address: "0x" + "11".repeat(20),
    to_address: "0x" + "22".repeat(20),
    value: "5000000",
    asset: "USDT",
    category: "erc20",
    direction: "in",
    raw_contract_address: "0x" + "33".repeat(20),
    raw_contract_value: "0x4c4b40",
    chain: "eth",
    ...overrides,
  };
}

function wrap(ui: ReactNode, initialEntries: string[]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ToastProvider>{ui}</ToastProvider>
    </MemoryRouter>,
  );
}

function wrapWithRoute(path: string, element: ReactNode) {
  return render(
    <MemoryRouter initialEntries={[`/wallets/${WALLET}`]}>
      <ToastProvider>
        <Routes>
          <Route path={path} element={element} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe("1. Fund flow — no stale 'Member 2 graph engine' copy", () => {
  it("renders an honest empty state instead of the 'requires Member 2' text", async () => {
    const { FundFlowDiagram } = await import("@/components/graph/FundFlowDiagram");
    render(<FundFlowDiagram path={EMPTY_PATH as never} />);
    expect(screen.getByText("No fund-flow path available for this investigation.")).toBeInTheDocument();
    expect(screen.queryByText(/Member 2/i)).toBeNull();
    expect(screen.queryByText(/graph engine/)).toBeNull();
  });

  it("renders a real path from the path object it is given", async () => {
    const { FundFlowDiagram } = await import("@/components/graph/FundFlowDiagram");
    render(
      <FundFlowDiagram
        path={{
          nodes: [
            { id: walletId, address: WALLET, type: "wallet", risk: "high" },
            { id: peerId, address: PEER, type: "vasp", risk: "unknown" },
          ],
          edges: [
            { id: "e0", source: walletId, target: peerId, transactionHash: `0x${"ee".repeat(32)}`, asset: "ETH", amount: "10.5", timestamp: "2026-01-01T00:00:00Z", blockNumber: 1 },
          ],
          metrics: { pathLength: 1, transactionCount: 1, totalValue: "10.5", asset: "ETH", timeElapsed: "—", confidence: 65 },
        }}
      />,
    );
    expect(screen.getByText("Path length: 1")).toBeInTheDocument();
    expect(screen.getByText(/Attribution caveat/i)).toBeInTheDocument();
  });
});

describe("2/3. Fund flow in the live graph page is honest and non-synthetic", () => {
  beforeEach(() => {
    mockLive = true;
    healthMock.mockReset();
    queryMock.mockReset();
    pathMock.mockReset();
    healthMock.mockResolvedValue({ status: "ok", provider: "neo4j" });
    queryMock.mockImplementation((q: { depth: number; address: string }) =>
      q.depth > 1 ? Promise.reject(new Error("GRAPH ENGINE UNAVAILABLE — test")) : Promise.resolve(graphFixture(q.address)),
    );
    pathMock.mockResolvedValue(EMPTY_PATH);
  });

  it("labels the flow tab with the live engine copy and shows no synthetic flow when no path exists", async () => {
    const { GraphPage } = await import("@/features/graph/GraphPage");
    wrap(<GraphPage />, [`/graph?tab=flow&address=${WALLET}&to=${PEER}`]);

    expect(await screen.findByText("Reconstructs movement of funds across the live Neo4j transaction graph.")).toBeInTheDocument();
    await screen.findByText("No fund-flow path available for this investigation.");
    expect(screen.queryByText(/Member 2/i)).toBeNull();
    // The full graph request is never fabricated into a fake flow.
    expect(healthMock).toHaveBeenCalled();
  });
});

describe("4. Risk UNKNOWN never references a future 'risk engine ships'", () => {
  it("renders honest 'no completed risk assessment' copy without 'ships' wording", async () => {
    const { RiskPage } = await import("@/features/risk/RiskPage");
    wrap(<RiskPage />, ["/risk"]);

    expect(await screen.findByText(/no completed risk assessment attached/i)).toBeInTheDocument();
    expect(screen.queryByText(/risk engine ships/i)).toBeNull();
    expect(screen.queryByText(/until the risk engine/i)).toBeNull();
    expect(screen.queryByText(/when the risk engine ships/i)).toBeNull();
  });
});

describe("5. SAHYOG status is honest (never 'Connected')", () => {
  it("shows 'integration-ready — production API not configured' on the dashboard status card", async () => {
    const { DashboardPage } = await import("@/features/dashboard/DashboardPage");
    wrap(<DashboardPage />, ["/dashboard"]);

    expect(await screen.findByText("System Status")).toBeInTheDocument();
    expect(screen.getByText("Integration-ready — production API not configured")).toBeInTheDocument();
    // The SAHYOG row must never claim a live connection to a production API
    // that is not configured.
    expect(screen.queryByText(/Sahyog intelligence. Connected/i)).toBeNull();
  });
});

describe("6/7. Investigator Assistant is present in navigation and opens", () => {
  it("appears in the left navigation and links to /assistant", async () => {
    const { Sidebar } = await import("@/components/layout/Sidebar");
    render(
      <MemoryRouter>
        <Sidebar open onClose={vi.fn()} />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: /Investigator Assistant/i });
    expect(link).toBeInTheDocument();
    expect(link.getAttribute("href")).toBe("/assistant");
  });

  it("opens and answers from a question", async () => {
    const { AssistantPage } = await import("@/features/assistant/AssistantPage");
    const { assistant } = await import("@/api/assistant");
    const user = userEvent.setup();
    wrap(<AssistantPage />, [`/assistant?wallet=${WALLET}`]);

    expect(await screen.findByLabelText("Assistant question")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Assistant question"), "review anything suspicious?");
    await user.click(screen.getByRole("button", { name: /^Ask$/ }));

    await waitFor(() => expect(assistant.query).toHaveBeenCalled());
    expect(await screen.findByText(/Grounded review body/i)).toBeInTheDocument();
  });
});

describe("8. Assistant uses the current investigation context", () => {
  it("pre-fills the selected case and passes its id + wallet to the query", async () => {
    mockLive = true;
    const { AssistantPage } = await import("@/features/assistant/AssistantPage");
    const { assistant } = await import("@/api/assistant");
    const { investigations } = await import("@/api/investigations");
    vi.mocked(investigations.list).mockResolvedValue([
      {
        id: "CT-2026-FINAL-001",
        name: "Final Audit Case",
        description: "d",
        primaryWallet: WALLET,
        network: "Ethereum",
        risk: "unknown",
        status: "investigating",
        transactions: 60,
        persistedTransactions: 53,
        vaspCandidates: 7,
        evidenceCount: 21,
        assignedAnalyst: "Audit Admin",
        createdAt: "2026-09-01T00:00:00Z",
        updatedAt: "2026-09-14T00:00:00Z",
        tags: [],
        isDemo: false,
      },
    ]);
    const user = userEvent.setup();
    wrap(<AssistantPage />, ["/assistant?case=CT-2026-FINAL-001"]);

    expect(await screen.findByLabelText("Assistant question")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Assistant question"), "summarize the case");
    await user.click(screen.getByRole("button", { name: /^Ask$/ }));

    await waitFor(() =>
      expect(assistant.query).toHaveBeenCalledWith(
        expect.objectContaining({
          caseId: "CT-2026-FINAL-001",
          walletAddress: WALLET,
        }),
      ),
    );
  });
});

describe("9/10/11. Focused mini-graph renders real depth-1 data and can open the full graph", () => {
  beforeEach(() => {
    mockLive = true;
    healthMock.mockReset();
    queryMock.mockReset();
    pathMock.mockReset();
    healthMock.mockResolvedValue({ status: "ok", provider: "neo4j" });
    queryMock.mockImplementation((q: { depth: number; address: string }) =>
      q.depth > 1 ? Promise.reject(new Error("full graph not needed")) : Promise.resolve(graphFixture(q.address)),
    );
    pathMock.mockResolvedValue(EMPTY_PATH);
  });

  it("centers the actual queried wallet (not a fallback/synthetic node)", async () => {
    const { GraphPage } = await import("@/features/graph/GraphPage");
    wrap(<GraphPage />, [`/graph?tab=focused&address=${WALLET}`]);

    const section = await screen.findByTestId("focused-section");
    expect(section.textContent).toContain("0x098b");
    const center = withinTree(section, "focused-center");
    expect(center).not.toBeNull();
    expect(healthMock).toHaveBeenCalled();
    // The mini graph is fed from a dedicated depth-1 query of the live engine.
    await waitFor(() => expect(queryMock).toHaveBeenCalledWith(expect.objectContaining({ depth: 1 })));
  });

  it("does not render synthetic wallet ids or demo fixture names in LIVE mode", async () => {
    const { GraphPage } = await import("@/features/graph/GraphPage");
    wrap(<GraphPage />, [`/graph?tab=focused&address=${WALLET}`]);

    await screen.findByTestId("focused-section");
    await waitFor(() => expect(queryMock).toHaveBeenCalled());
    expect(screen.queryByText(/wallet_001/i)).toBeNull();
    expect(screen.queryByText(/0x000.*000/i)).toBeNull();
    expect(screen.queryByText(/Rohan/i)).toBeNull();
    expect(screen.queryByText(/Meera/i)).toBeNull();
    expect(screen.queryByText(/StakingPool/i)).toBeNull();
    expect(screen.queryByText(/SYNTHETIC/i)).toBeNull();
  });

  it("offers an 'Open in full graph →' affordance from the focused view", async () => {
    const { GraphPage } = await import("@/features/graph/GraphPage");
    wrap(<GraphPage />, [`/graph?tab=focused&address=${WALLET}`]);

    const openFull = await screen.findByRole("button", { name: /Open in full graph/i });
    expect(openFull).toBeInTheDocument();
  });

  it("emits the clicked node so the parent can focus the full graph on it", async () => {
    const { FocusedGraph } = await import("@/components/graph/FocusedGraph");
    const onNodeClick = vi.fn();
    render(
      <FocusedGraph
        nodes={[
          { id: walletId, address: WALLET, type: "wallet", risk: "high" },
          { id: peerId, address: PEER, type: "vasp", risk: "unknown" },
        ]}
        edges={[{ id: "e0", source: walletId, target: peerId, transactionHash: `0x${"ee".repeat(32)}`, asset: "ETH", amount: "10.5", timestamp: "2026-01-01T00:00:00Z", blockNumber: 1 }]}
        centerId={walletId}
        onNodeClick={onNodeClick}
      />,
    );
    const user = userEvent.setup();
    const neighbor = screen.getByTestId("focused-neighbor");
    await user.click(neighbor);
    await waitFor(() => expect(onNodeClick).toHaveBeenCalledWith(expect.objectContaining({ id: peerId })));
  });
});

describe("12/13/14. LIVE mode uses real data, no stale fixtures, no request storm", () => {
  beforeEach(() => {
    mockLive = true;
    healthMock.mockReset();
    queryMock.mockReset();
    pathMock.mockReset();
    healthMock.mockResolvedValue({ status: "ok", provider: "neo4j" });
    queryMock.mockImplementation((q: { depth: number; address: string }) =>
      q.depth > 1 ? Promise.reject(new Error("full graph not needed")) : Promise.resolve(graphFixture(q.address)),
    );
    pathMock.mockResolvedValue(EMPTY_PATH);
  });

  it("issues exactly one live graph probe and one focused query for a page open (no loop)", async () => {
    const { GraphPage } = await import("@/features/graph/GraphPage");
    wrap(<GraphPage />, [`/graph?tab=focused&address=${WALLET}`]);

    await screen.findByTestId("focused-section");
    await waitFor(() => expect(queryMock).toHaveBeenCalledTimes(1));
    expect(healthMock).toHaveBeenCalledTimes(1);
    // Let any spurious effect settle and confirm nothing re-fires by itself.
    await new Promise((r) => setTimeout(r, 100));
    expect(queryMock).toHaveBeenCalledTimes(1);
    expect(healthMock).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/SYNTHETIC GRAPH DATA/i)).toBeNull();
  });
});

describe("13b. Wallet transaction rows label latest ingestion vs persisted history", () => {
  beforeEach(() => {
    mockLive = true;
    walletSummaryMock.mockReset();
    walletTransfersMock.mockReset();
    walletSummaryMock.mockResolvedValue({
      address: WALLET,
      network: "Ethereum",
      firstSeen: null,
      lastActivity: null,
      transactionCount: 5,
      incomingVolume: "0",
      outgoingVolume: "0",
      balance: null,
      risk: "unknown",
      riskScore: null,
      investigationStatus: "not_analyzed",
    });
  });

  it('shows "Persisted investigation history: N held transfers" when served from the store', async () => {
    walletTransfersMock.mockResolvedValue({
      wallet_address: WALLET,
      chain: "eth",
      transfers: [makeTransfer(), makeTransfer({ direction: "out", value: "200", asset: "ETH" })],
      pagination: {
        max_transfers: 10000,
        fetched: 5,
        truncated: false,
        offset: 0,
        limit: 25,
        total: 5,
        has_next: false,
        has_previous: false,
        source: "database",
      },
    });
    const { WalletDetailPage } = await import("@/features/wallets/WalletDetailPage");
    wrapWithRoute("/wallets/:address", <WalletDetailPage />);

    const label = await screen.findByTestId("tx-history-label");
    await waitFor(() => expect(label.textContent).toContain("Persisted investigation history: 5 held transfers"));
  });

  it('shows "Latest ingestion: N new/returned transfers" when provider-fetched', async () => {
    walletTransfersMock.mockResolvedValue({
      wallet_address: WALLET,
      chain: "eth",
      transfers: [makeTransfer(), makeTransfer({ direction: "out" }), makeTransfer({ asset: "ETH" })],
      pagination: {
        max_transfers: 10000,
        fetched: 3,
        truncated: true,
        offset: 0,
        limit: 25,
        total: 3,
        has_next: false,
        has_previous: false,
        source: "provider",
      },
    });
    const { WalletDetailPage } = await import("@/features/wallets/WalletDetailPage");
    wrapWithRoute("/wallets/:address", <WalletDetailPage />);

    const label = await screen.findByTestId("tx-history-label");
    await waitFor(() => expect(label.textContent).toContain("Latest ingestion: 3 new/returned transfers"));
  });
});

// Helper: find a descendant by testid without requiring the root element.
function withinTree(root: Element, testid: string): Element | null {
  return root.querySelector(`[data-testid="${testid}"]`);
}