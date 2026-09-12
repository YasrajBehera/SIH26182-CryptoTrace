import { isDemoMode } from "./config";
import { getToken } from "@/auth/tokenStore";
import type { ReportConfig, ReportSectionKey } from "./types";

/**
 * Report service contract.
 *
 * In live mode the server renders the PDF (POST /api/v1/reports/export) and
 * streams application/pdf bytes that carry an X-CryptoTrace-Report-Id header.
 * Missing investigation data is marked UNAVAILABLE server-side so the artefact
 * never implies information the system did not hold. In demo mode the browser
 * export (print stylesheet) remains the path.
 */

export interface ReportExportResult {
  url: string;
  reportId: string;
}

function toSnakeCaseMetadata(config: ReportConfig): Record<string, unknown> {
  const meta = config.metadata;
  return {
    case_id: meta.caseId || null,
    case_name: meta.caseName,
    investigator: meta.investigator,
    generated_at: meta.generatedAt,
    classification: meta.classification,
    network: meta.network.toLowerCase() === "ethereum" ? "eth" : meta.network.toLowerCase(),
    primary_wallet: meta.primaryWallet || null,
  };
}

async function fetchReportBlob(config: ReportConfig): Promise<{ blob: Blob; reportId: string }> {
  const authToken = getToken();
  const res = await fetch("/api/v1/reports/export", {
    method: "POST",
    headers: {
      Accept: "application/pdf",
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: JSON.stringify({ metadata: toSnakeCaseMetadata(config), sections: config.sections }),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = (await res.json()) as { detail?: string };
      detail = body?.detail ?? "";
    } catch {
      // Non-JSON errors keep the generic message.
    }
    throw new Error(detail || `The report service could not generate the PDF (HTTP ${res.status}).`);
  }
  const blob = await res.blob();
  const reportId = res.headers.get("X-CryptoTrace-Report-Id") ?? `rpt-${Date.now()}`;
  return { blob, reportId };
}

export const reports = {
  /** Server-side PDF export; returns a blob URL ready for download. */
  async exportPdf(config: ReportConfig): Promise<ReportExportResult> {
    if (isDemoMode()) throw new Error("Server-side PDF export is unavailable in demo mode. Use the browser export.");
    const { blob, reportId } = await fetchReportBlob(config);
    const url = URL.createObjectURL(blob);
    return { url, reportId };
  },

  async sections(): Promise<ReportSectionKey[]> {
    const res = await fetchReportSections();
    return res;
  },
};

async function fetchReportSections(): Promise<ReportSectionKey[]> {
  const authToken = getToken();
  const res = await fetch("/api/v1/reports/sections", {
    headers: { Accept: "application/json", ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}) },
  });
  if (!res.ok) return [];
  const body = (await res.json()) as { sections?: ReportSectionKey[] };
  return body?.sections ?? [];
}