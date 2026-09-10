import type { ReactNode } from "react";
import type { ActivityEvent } from "@/api/types";
import { fromNow } from "@/lib/format";
import { Badge } from "./Badges";

const ACTION_LABEL: Record<ActivityEvent["action"], string> = {
  wallet_investigated: "Wallet investigated",
  transaction_imported: "Transaction imported",
  graph_requested: "Graph analysis requested",
  vasp_candidate: "VASP candidate generated",
  evidence_attached: "Evidence attached",
  risk_changed: "Risk score changed",
  report_generated: "Report generated",
  investigation_updated: "Investigation updated",
};

const SEV_DOT: Record<ActivityEvent["severity"], string> = {
  info: "status-dot ok",
  success: "status-dot ok",
  warning: "status-dot warn",
  critical: "status-dot error",
};

interface TimelineProps {
  events: ActivityEvent[];
  max?: number;
}

export function Timeline({ events, max }: TimelineProps) {
  const shown = max ? events.slice(0, max) : events;
  if (!shown.length) return null;
  return (
    <ol className="timeline" style={{ listStyle: "none" }}>
      {shown.map((e) => (
        <li key={e.id} className="timeline-item">
          <span className="timeline-dot" aria-hidden>
            <span className={SEV_DOT[e.severity]} />
          </span>
          <div className="timeline-body">
            <div className="timeline-title">{ACTION_LABEL[e.action]}</div>
            <div className="timeline-meta">
              <span title={e.at}>{fromNow(e.at)}</span>
              <span>·</span>
              <span>{e.actor}</span>
              <span>·</span>
              <Badge className="status-open">{e.caseId}</Badge>
              {e.isDemo ? <Badge className="badge-demo">Demo</Badge> : null}
            </div>
            {e.detail ? <div className="timeline-meta" style={{ marginTop: 4 }}>{e.detail}</div> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function SimpleTimeline({ items }: { items: Array<{ id: string; at: string; actor: string; title: ReactNode; meta?: ReactNode }> }) {
  return (
    <ol className="timeline" style={{ listStyle: "none" }}>
      {items.map((it) => (
        <li key={it.id} className="timeline-item">
          <span className="timeline-dot" aria-hidden>
            <span className="status-dot ok" />
          </span>
          <div className="timeline-body">
            <div className="timeline-title">{it.title}</div>
            <div className="timeline-meta">
              <span>{fromNow(it.at)}</span>
              <span>·</span>
              <span>{it.actor}</span>
            </div>
            {it.meta ? <div className="timeline-meta">{it.meta}</div> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}