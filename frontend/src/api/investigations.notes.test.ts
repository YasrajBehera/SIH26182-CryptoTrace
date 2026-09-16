import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({
  client: { get: vi.fn(), post: vi.fn() },
  ApiError: class ApiError extends Error {
    status = 0;
    code = "";
    safe = true;
  },
}));
vi.mock("./config", () => ({ isDemoMode: vi.fn() }));
vi.mock("@/mock", () => ({
  demoNotes: [] as Array<{ id: string; author: string; createdAt: string; body: string }>,
  demoActivity: [],
  demoTimeline: [],
  getDemoInvestigations: () => [],
  getDemoInvestigation: () => undefined,
  getDemoInvestigationAnalysis: () => ({ candidates: [], evidence: [] }),
  addDemoInvestigation: () => {},
}));
vi.mock("./analysis", () => ({
  mapBackendEvidenceToItem: (e: { evidence_id: string }) => ({ id: e.evidence_id }),
  mapInvestigationResult: (raw: Record<string, unknown>, ev: unknown[]) => ({ ...raw, evidence: ev }),
}));

import { client } from "./client";
import { isDemoMode } from "./config";
import { demoNotes } from "@/mock";
import { investigations } from "./investigations";

const getMock = vi.mocked(client.get);
const postMock = vi.mocked(client.post);
const demoMode = vi.mocked(isDemoMode);

describe("investigation notes (live mode)", () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    demoMode.mockReset().mockReturnValue(false);
  });

  it("loads persisted notes and maps backend fields to the view model", async () => {
    getMock.mockResolvedValue({
      notes: [
        { id: "note-1", case_id: "CT-1", author: "Rohan", body: "Trail observed", created_at: "2026-09-10T08:00:00Z" },
      ],
      total: 1,
      case_id: "CT-1",
    });

    const notes = await investigations.notes("CT-1");

    expect(getMock).toHaveBeenCalledWith("/api/v1/investigations/CT-1/notes", { signal: undefined });
    expect(notes).toEqual([
      { id: "note-1", author: "Rohan", body: "Trail observed", createdAt: "2026-09-10T08:00:00Z" },
    ]);
  });

  it("persists a note via POST and maps the created record", async () => {
    postMock.mockResolvedValue({
      id: "note-2",
      case_id: "CT-1",
      author: "Meera",
      body: "Second observation",
      created_at: "2026-09-10T09:00:00Z",
    });

    const note = await investigations.addNote("CT-1", "Second observation", "Meera");

    expect(postMock).toHaveBeenCalledWith("/api/v1/investigations/CT-1/notes", {
      body: "Second observation",
      author: "Meera",
    });
    expect(note.createdAt).toBe("2026-09-10T09:00:00Z");
    expect(note.body).toBe("Second observation");
  });
});

describe("investigation notes (demo mode)", () => {
  beforeEach(() => {
    demoMode.mockReset().mockReturnValue(true);
    demoNotes.length = 0;
    getMock.mockReset();
    postMock.mockReset();
  });

  it("returns the labeled synthetic notes without calling the backend", async () => {
    demoNotes.push({ id: "n-demo", author: "Rohan Iyer", createdAt: "2026-01-01T00:00:00Z", body: "Demo note" });
    const notes = await investigations.notes("CT-2026-0142");
    expect(notes).toHaveLength(1);
    expect(getMock).not.toHaveBeenCalled();
  });

  it("appends to the synthetic set without calling the backend", async () => {
    const note = await investigations.addNote("CT-2026-0142", "New trail", "Rohan Iyer");
    expect(note.body).toBe("New trail");
    expect(note.author).toBe("Rohan Iyer");
    expect(demoNotes).toHaveLength(1);
    expect(postMock).not.toHaveBeenCalled();
  });
});