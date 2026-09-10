import { isDemoMode } from "./config";
import type { ReportConfig } from "./types";

/**
 * Report service contract.
 *
 * PDF generation architecture: today the browser is the exporter
 * (`window.print()` drives the print stylesheet in styles/components2.css).
 * A future backend report service can adopt the same ReportConfig contract
 * and return a PDF binary. Nothing in the UI claims cryptographic
 * verification of exports.
 */
export const reports = {
  /** Placeholder for a server-side PDF export endpoint. */
  async exportPdf(_config: ReportConfig): Promise<{ url: string }> {
    if (isDemoMode()) throw new Error("Server-side PDF export is not implemented yet. Use the browser export.");
    throw new Error("Server-side PDF export is not implemented yet. Use the browser export.");
  },
};