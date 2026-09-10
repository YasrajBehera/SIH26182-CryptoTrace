import { useNavigate } from "react-router-dom";
import { PageHeader, Button, Card, DemoBadge, ShortAddress, UnauthorizedState } from "@/components/ui";
import { WalletIcon, AddIcon } from "@/components/icons";
import { WalletQuickLook } from "@/components/wallets/WalletQuickLook";
import { InvestigationWorkflow } from "@/components/investigations/InvestigationWorkflow";
import { demoWallets } from "@/mock";
import { useAuth } from "@/auth/AuthContext";

export function WalletExplorerPage() {
  const navigate = useNavigate();
  const { can } = useAuth();

  if (!can("wallet.read")) {
    return (
      <div className="page">
        <PageHeader title="Wallet Explorer" />
        <UnauthorizedState />
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        title="Wallet Explorer"
        subtitle="Investigate a public wallet: load normalized transfers, review flows, and open analysis tools."
        crumbs={[{ label: "Wallet Explorer" }]}
      />

      <Card title="Investigate a wallet" subtitle="Uses the live Member 1 ingestion endpoint when reachable; otherwise labeled demo data.">
        <WalletQuickLook />
      </Card>

      <Card title="Recent demo wallets" subtitle="Convenient synthetic addresses for trying the workflow (clearly marked DEMO)." actions={<DemoBadge />}>
        <div className="grid grid-4" style={{ gap: 8 }}>
          {demoWallets.map((w) => (
            <button key={w} className="flow-step" style={{ cursor: "pointer", justifyContent: "space-between" }} onClick={() => navigate(`/wallets/${w}`)}>
              <ShortAddress address={w} />
              <WalletIcon />
            </button>
          ))}
        </div>
      </Card>

      <Card title="Workflow" subtitle="Typical investigator path — each step follows the same evidence pipeline.">
        <InvestigationWorkflow active={0} />
        <div className="row" style={{ marginTop: 12 }}>
          <Button variant="primary" leading={<AddIcon />} onClick={() => navigate("/investigations?new=1")}>
            New Investigation
          </Button>
        </div>
      </Card>
    </div>
  );
}