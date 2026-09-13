import { client, type BlobResult } from "./client";
import { isDemoMode } from "./config";
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
  // The central client attaches the bearer token, normalizes errors, and fires
  // cryptotrace:unauthorized on a 401 so the session layer re-authenticates.
  const res = await client.postBlob<BlobResult>(
    "/api/v1/reports/export",
    { metadata: toSnakeCaseMetadata(config), sections: config.sections },
    { headers: { Accept: "application/pdf" }, timeoutMs: 120000 },
  );
  const reportId = res.headers.get("X-CryptoTrace-Report-Id") ?? `rpt-${Date.now()}`;
  return { blob: res.blob, reportId };
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
  const body = await client.get<{ sections?: ReportSectionKey[] }>("/api/v1/reports/sections");
  return body?.sections ?? [];
}