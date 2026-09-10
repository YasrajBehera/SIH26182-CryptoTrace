import type { ReactNode } from "react";
import {
  EvidenceIcon,
  GraphIcon,
  ReportIcon,
  RiskIcon,
  TraceIcon,
  TxIcon,
  VaspIcon,
  WalletIcon,
} from "@/components/icons";

/**
 * Visual representation of the CryptoTrace investigation pipeline.
 * Every case follows the same evidence-first narrative:
 *
 *   Wallet → Blockchain Activity → Transaction Graph → Fund Flow →
 *   VASP Candidates → Evidence → Confidence → Investigation Report
 *
 * `active` highlights the step the investigator is currently working on
 * (0-based). All steps are shown so the path to a finding is always obvious.
 */

interface Stage {
  label: string;
  hint: string;
  icon: ReactNode;
}

const STAGES: Stage[] = [
  { label: "Wallet", hint: "Identify subject", icon: <WalletIcon /> },
  { label: "Blockchain Activity", hint: "Pull on-chain transfers", icon: <TxIcon /> },
  { label: "Transaction Graph", hint: "Map relationships", icon: <GraphIcon /> },
  { label: "Fund Flow", hint: "Reconstruct movement", icon: <TraceIcon /> },
  { label: "VASP Candidates", hint: "Score associations", icon: <VaspIcon /> },
  { label: "Evidence", hint: "Collect provenance", icon: <EvidenceIcon /> },
  { label: "Confidence", hint: "Assess strength", icon: <RiskIcon /> },
  { label: "Investigation Report", hint: "Document findings", icon: <ReportIcon /> },
];

export function InvestigationWorkflow({ active = -1 }: { active?: number }) {
  const current = Math.max(-1, Math.min(active, STAGES.length - 1));

  return (
    <ol className="workflow-track" aria-label="Investigation workflow">
      {STAGES.map((stage, i) => {
        const state = current > i ? "done" : current === i ? "active" : "pending";
        return (
          <li key={stage.label} className={`workflow-step ${state}`}>
            <span className="workflow-node">
              <span className="workflow-icon" aria-hidden>
                {stage.icon}
              </span>
              <span className="workflow-copy">
                <span className="workflow-label">{stage.label}</span>
                <span className="workflow-hint">{stage.hint}</span>
              </span>
            </span>
            {i < STAGES.length - 1 ? (
              <span className="workflow-arrow" aria-hidden>
                ›
              </span>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}