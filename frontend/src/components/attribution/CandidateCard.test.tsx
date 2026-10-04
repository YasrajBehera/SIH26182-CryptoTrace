import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CandidateCard } from "@/components/attribution/CandidateCard";
import { EvidenceCard } from "@/components/evidence/EvidenceComponents";
import type { AttributionCandidate, EvidenceItem } from "@/api/types";

/**
 * A candidate must name the chain it was analysed on. The same 20-byte hex
 * string on a different EVM chain is a different account, so a Ronin result
 * rendered as "Ethereum" is a factual error, not a cosmetic one.
 */
const RONIN_WALLET = "0x7a4f5c3d2e1b0a9f8e7d6c5b4a3928170f6e5d4c";
const BITGET_RONIN = "0x5bdf85216ec1e38d6458c870992a69e38e03f7ef";
const BITGET_TX =
  "0x733fc397a5a565a5f4ee16f15f420640a1a77982a87f12145634abf3e41ca8b2";

function candidate(overrides: Partial<AttributionCandidate> = {}): AttributionCandidate {
  return {
    id: "cand-ronin-0",
    wallet: RONIN_WALLET,
    chain: "ronin",
    vaspName: "Bitget",
    confidenceLevel: "medium",
    confidenceScore: 40,
    state: "medium_confidence",
    evidenceCount: 1,
    relatedAddresses: [],
    transactionVolume: "—",
    asset: "",
    firstInteraction: null,
    lastInteraction: null,
    risk: "unknown",
    reasoning: "Observed a transaction with a publicly labelled address.",
    factors: [],
    evidenceIds: ["ev-ronin-1"],
    isDemo: false,
    ...overrides,
  };
}

function evidenceItem(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: "ev-ronin-1",
    type: "transaction_flow",
    title: "Transaction flow evidence",
    source: "chain",
    createdBy: "attribution_engine",
    createdAt: "2026-01-01T00:00:00Z",
    relatedWallet: RONIN_WALLET,
    relatedTransaction: BITGET_TX,
    chain: "ronin",
    matchedAddress: BITGET_RONIN,
    analysisId: "attr-ronin",
    timestamp: null,
    limitations: [
      "A public directory label is an investigative lead. It does not by itself establish legal ownership, control, or the identity of the operator.",
    ],
    reliability: "high",
    notes: "Bitget observed on Ronin, direction out, value 2770.21 RON.",
    isDemo: false,
    ...overrides,
  };
}

describe("CandidateCard shows the analysed chain", () => {
  it("labels a Ronin candidate as Ronin, never as Ethereum", () => {
    render(<CandidateCard candidate={candidate()} />);

    expect(screen.getByText("Bitget")).toBeInTheDocument();
    expect(screen.getByText("Ronin")).toBeInTheDocument();
    expect(screen.queryByText("Ethereum")).not.toBeInTheDocument();
  });

  it("keeps an Ethereum candidate labelled Ethereum", () => {
    render(<CandidateCard candidate={candidate({ chain: "eth", wallet: "0x" + "aa".repeat(20) })} />);

    expect(screen.getByText("Ethereum")).toBeInTheDocument();
    expect(screen.queryByText("Ronin")).not.toBeInTheDocument();
  });

  it("shows a chain alias under its own name, not as a raw id", () => {
    render(<CandidateCard candidate={candidate({ chain: "ronin-mainnet" })} />);

    expect(screen.getByText("Ronin")).toBeInTheDocument();
    expect(screen.queryByText("ronin-mainnet")).not.toBeInTheDocument();
  });
});

describe("EvidenceCard exposes what the evidence does not prove", () => {
  it("renders the matched VASP address with its chain", () => {
    render(
      <MemoryRouter>
        <EvidenceCard item={evidenceItem()} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Matched address")).toBeInTheDocument();
    // Shortened for display, but the full address stays reachable (copy button).
    expect(screen.getByText(/0x5bdf/)).toBeInTheDocument();
    expect(
      screen.getByLabelText(`Copy address ${BITGET_RONIN}`),
    ).toBeInTheDocument();
  });

  it("renders the ownership limitation verbatim", () => {
    render(
      <MemoryRouter>
        <EvidenceCard item={evidenceItem()} />
      </MemoryRouter>,
    );

    expect(
      screen.getByText(/does not by itself establish legal ownership/),
    ).toBeInTheDocument();
    expect(screen.getByText("What this evidence does NOT establish")).toBeInTheDocument();
  });

  it("omits the limitations block when a record has none", () => {
    render(
      <MemoryRouter>
        <EvidenceCard item={evidenceItem({ limitations: [] })} />
      </MemoryRouter>,
    );

    expect(
      screen.queryByText("What this evidence does NOT establish"),
    ).not.toBeInTheDocument();
  });

  it("shows live chain provenance rather than a demo label", () => {
    render(
      <MemoryRouter>
        <EvidenceCard item={evidenceItem()} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Blockchain · Ronin")).toBeInTheDocument();
    expect(screen.queryByText("Synthetic demo data")).not.toBeInTheDocument();
  });
});