# Phase 39 — Finalization Report

Status: SUBMISSION-READY (all automated checks green)

## Scope

Closing sprint for SIH26182-CryptoTrace. Three items were finished so the
platform ships a coherent, evidence-grounded investigation workflow:

1. **M9 — Investigator Assistant (rule-based).** Deterministic, LLM-free assistant
   whose every answer is derived from investigation data already in the system:
   - 12 quick actions across case summaries, risk explanations, attribution,
     wallet/VASP lookups, transaction timelines and draft referrals.
   - Intent parsing (EN + ZH), per-intent renderers, and graph/timeline tooling.
   - Every response carries `human_review_required: true` and a truthful
     `data_source` (`live`/`synthetic`/`mixed`) derived from evidence — never assumed.
   - Referrals are draft-only (`submission_state: "requires_sahyog_connection"`);
     the assistant never submits enforcement action autonomously.
   - Backend: `assistant` package mounted under `/api/v1/assistant`, gated by
     `investigation.read`, every query audited (`ASSISTANT_QUERY`).
   - Frontend: `InvestigatorAssistant` component on the Case detail ("Assistant"
     tab) and Wallet detail pages, with confirmed-action gating for destructive
     intents and synthetic labeling in demo mode.

2. **M8 — Persisted case notes.** Cases now carry an analyst note stream:
   - New `investigation_notes` table + idempotent migration on boot.
   - `GET/POST /api/v1/investigations/{case_id}/notes`, ownership-scoped
     (`investigation.read` / `investigation.update`), audited
     (`CASE_NOTE_LIST`, `CASE_NOTE_CREATE`).
   - Frontend notes tab now reads live notes and persists new ones (demo mode
     appends to clearly-labeled synthetic notes).

3. **M6-D — Graph edge block number.** BFS/neighbor edges now expose the
   on-chain `block_number` of each recorded transfer (backend query + schema,
   frontend wire/view types, edge card rendering).

## Verification

| Check | Result |
| --- | --- |
| Backend test suite (`pytest -q`) | 485 passed, 5 skipped, 2 warnings |
| New backend tests this phase | assistant (34), case notes (5), graph `block_number` |
| Frontend test suite (`npm test`) | 94 passed across 14 files |
| `npm run typecheck` | clean |
| `npm run lint` (`--max-warnings 0`) | clean |
| `npm run build` | clean (Vite production bundle) |
| Hermeticity | full suite runs offline — no Alchemy key, Postgres, Neo4j, Redis, or network required |

Key regression-guard: the assistant test wiring injects fresh in-memory
repositories shared between `InvestigationService` and `AssistantTools`, so no
module-singleton leakage can silently connect tools to different data.

## Honesty guarantees (unchanged)

- The UI never claims LIVE when data is synthetic; demo/synthetic/source badges
  are derived, not asserted.
- Attribution is stated as a ranked analytical heuristic ("transactional
  association"), not proof of wallet ownership.
- Neo4j-unavailable and provider-unavailable states render truthfully
  (UNAVAILABLE / synthetic fallback badges).
- SAHYOG remains DEMO/INTEGRATION-READY; no submission is sent anywhere.

## Known gaps (by design, documented)

- Server-side PDF export — browser print/preview only (`NOT CONFIGURED`).
- SAHYOG live adapter — draft referrals only until the partner environment exists.
- Hosted Neo4j — the graph API runs against a local instance; the health probe
  reports `synthetic` honestly when it is down.

## Run

```powershell
# backend (from repo root or backend/)
python -m pytest                      # 485 passed, 5 skipped
# frontend
npm test                              # 94 passed
npm run lint && npm run typecheck && npm run build

# live run
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

Real wallet used for manual E2E: `0xFB74767C1ce1aadA0a0E114441173b57f8C1571b`.