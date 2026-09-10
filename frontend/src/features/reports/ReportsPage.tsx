import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader, Button, Card, DemoBadge, Badge, Input, Field, EmptyState, LoadingBlock } from "@/components/ui";
import { ExportIcon } from "@/components/icons";
import { ReportSectionSelector, ReportPreview, ALL_REPORT_SECTIONS } from "@/components/reports/ReportComponents";
import { useApi } from "@/hooks/useApi";
import { investigations } from "@/api/investigations";
import { wallets } from "@/api/wallets";
import { attribution } from "@/api/attribution";
import { evidence } from "@/api/evidence";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import type { ReportConfig, ReportSectionKey } from "@/api/types";
import { validateAddressInput } from "@/lib/address";

export function ReportsPage() {
  const [params, setParams] = useSearchParams();
  const { isDemo } = useDataSource();
  const { user, can } = useAuth();

  const caseParam = params.get("case") ?? "";
  const walletParam = params.get("wallet") ?? "";
  const [target, setTarget] = useState(walletParam);

  const [sections, setSections] = useState<ReportSectionKey[]>(ALL_REPORT_SECTIONS);

  const targetValid = target && validateAddressInput(target) === null;

  const { data: caseData } = useApi(
    () => (caseParam ? investigations.get(caseParam) : Promise.resolve(null)),
    [caseParam],
  );

  const { data: transfers } = useApi(
    () => (targetValid ? wallets.getTransfers(target, 500).then((r) => r.transfers) : Promise.resolve([])),
    [target],
  );

  const { data: candidates } = useApi(() => attribution.candidates(targetValid ? target : undefined), [target]);
  const { data: evidenceItems } = useApi(() => evidence.list(targetValid ? target : undefined), [target]);
  const { data: timeline } = useApi(() => investigations.timeline(), []);

  const walletAddress = caseData?.primaryWallet ?? (targetValid ? target : "");
  const network = caseData?.network ?? "Ethereum";

  const toggleSection = (key: ReportSectionKey) => {
    setSections((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  };

  const config = useMemo<ReportConfig>(
    () => ({
      metadata: {
        caseId: caseData?.id ?? `CT-${target.slice(0, 6).toUpperCase()}-NWP`,
        caseName: caseData?.name ?? "Wallet analysis",
        investigator: user?.name ?? "Unassigned",
        generatedAt: new Date().toISOString(),
        classification: "INTERNAL / LAW ENFORCEMENT COOPERATION",
        network,
        primaryWallet: walletAddress,
      },
      sections,
    }),
    [caseData, user, network, walletAddress, sections, target],
  );

  if (!can("report.create")) {
    return (
      <div className="page">
        <PageHeader title="Reports" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>Your role does not permit generating reports.</p>
        </Card>
      </div>
    );
  }

  const exportPdf = () => {
    window.print();
  };

  return (
    <div className="page">
      <PageHeader
        title="Reports"
        subtitle="Build and export a case report. The preview is browser-rendered; server-side PDF export is pending."
        crumbs={[{ label: "Reports" }]}
        actions={
          <>
            {isDemo ? <DemoBadge label="DEMO REPORT PREVIEW" /> : <Badge className="status-open">Live</Badge>}
            <Button variant="primary" leading={<ExportIcon />} onClick={exportPdf} disabled={!walletAddress}>
              Export PDF (print)
            </Button>
          </>
        }
      />

      <Card title="Report scope">
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            setParams(targetValid ? { wallet: target } : {});
          }}
        >
          <Field
            label="Primary wallet"
            htmlFor="report-wallet"
            hint={caseParam ? `Pre-filled from case ${caseParam}.` : "Leave empty if no wallet data should be included."}
          >
            <Input
              id="report-wallet"
              className="mono"
              value={target}
              invalid={!!target && !targetValid}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="0x…"
            />
          </Field>
          <div className="table-toolbar">
            <Badge className="status-draft">
              Case: {caseData?.id ?? "no case linked"} · Network: {network}
            </Badge>
            <Badge className="status-draft">{transfers?.length ?? 0} transfers</Badge>
            <Badge className="status-draft">{candidates?.length ?? 0} VASP candidates</Badge>
            <Badge className="status-draft">{evidenceItems?.length ?? 0} evidence items</Badge>
          </div>
        </form>
      </Card>

      {!walletAddress ? (
        <EmptyState
          title="No wallet selected"
          description="Open this page from a wallet or case, or type an address above, to generate a report."
        />
      ) : (
        <>
          <Card title="Sections" subtitle="Toggle which sections the report includes.">
            <ReportSectionSelector sections={sections} onToggle={toggleSection} />
          </Card>

          {!transfers && !candidates ? (
            <LoadingBlock label="Loading report data…" />
          ) : (
            <Card
              title="Report preview"
              subtitle="Scoped preview — verify content before export."
              actions={<Button size="sm" onClick={exportPdf}>Print / save as PDF</Button>}
              bodyClassName="report-scroll"
            >
              <ReportPreview
                config={config}
                data={{ investigation: caseData, transfers: transfers ?? [], candidates: candidates ?? [], evidence: evidenceItems ?? [], timeline: timeline ?? [] }}
                mode={isDemo ? "demo" : "live"}
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}