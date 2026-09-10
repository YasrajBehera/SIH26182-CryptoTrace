# Frontend — Member 4

Role: **Frontend + UI/UX + Security**. React + TypeScript + Vite implementation of
the SIH26182-CryptoTrace blockchain investigation platform UI.

## Implemented

- Dark enterprise design system with semantic design tokens (`src/styles/tokens.css`)
  and hand-rolled charts (SVG) — zero chart dependency.
- Global app shell: responsive sidebar, topbar, global search (`/` shortcut),
  DEMO/LIVE data banner, session-timeout modal.
- Pages: login, dashboard, wallet explorer + wallet detail, global transaction
  explorer, investigations (list/new/detail), transaction graph (React Flow),
  VASP intelligence, evidence workspace + provenance, risk analysis, report
  builder + print export, audit log, admin (users / roles / settings), 404.
- Wallet explorer against the **live Member 1 API**:
  `GET /api/v1/wallets/:address/transfers` (with native transfer drawer, filters,
  demo fallback when backend is unreachable).
- RBAC session UI: 5 demo roles with permission matrix; `ProtectedRoute`;
  route-level `PermissionBoundary` in `App.tsx` + RBAC-gated sidebar nav;
  session in sessionStorage (user id only — never credentials).
- Tests (Vitest + Testing Library) and full toolchain checks
  (`typecheck`, `lint --max-warnings 0`, `test`, `build`).
- Route-level code splitting: every page is `React.lazy`; the React Flow
  (graph) chunk (~195 kB) is isolated from the initial bundle (~217 kB).

## Second engineering pass (security/UX/deep-integration)

- **Dashboard workstation**: investigation control bar (search, network, risk,
  status, update-window filters) that genuinely narrows the case table and risk
  chart; honest per-engine system status card; fund-flow preview with
  interactive nodes; evidence + VASP-candidate snapshots that deep-link via
  `?focus=` / `?wallet=`; demo metrics explicitly labeled `DEMO`. The
  `_EvidenceIcon` export hack was removed.
- **RBAC at route + sidebar level** using the demo permission grid
  (`evidence.read`, `risk.read` added to the grid). Frontend RBAC is explicitly
  a convenience guard — the backend remains the authorization authority.
- **Evidence**: detail rows now include `relatedCandidate`; delete is gated by
  `evidence.delete` and calls `evidence.delete()` (throws unless demo);
  `?focus=<id>` scrolls-to and highlights an item (used by global search and the
  dashboard snapshot).
- **Transaction explorer**: date-range filter (`from`/`to`), `?hash=` initial
  filter, direction/asset/min-amount filters, `wallet.read` gate.
- **Graph**: time-range filter (All/30/90/365 days), bidirectional edge
  highlighting, node legend, interactive fund-flow nodes that deep-link to the
  graph.
- **Wallet UX**: copy-address button; `wallet.read` gates on explorer + detail.
- **A11y**: sortable `DataTable` headers are keyboard accessible
  (`role="button"`, Enter/Space, `aria-sort`); report section selector now uses
  a real label + hidden checkbox + `.switch` (no `Switch` component).

## Not implemented / waiting for backend

| Feature | Status | Notes |
| --- | --- | --- |
| Case persistence | MOCKED | Backend has only a legacy `POST /investigations` stub |
| Graph engine (Member 2, Neo4j) | MOCKED | `src/api/graph.ts` returns labeled synthetic data |
| VASP attribution (Member 3) | MOCKED | `src/api/attribution.ts` returns labeled candidates |
| Evidence store (Member 3) | MOCKED | `src/api/evidence.ts` returns labeled evidence |
| Audit backend | MOCKED | `src/api/evidence.ts#audit` demo events |
| Server-side PDF export | PENDING | Browser `window.print()` is used today |
| Auth on backend | PENDING | Frontend demo auth only; backend is the future authority |
| Investigation risk scoring | WAITING FOR BACKEND | UI renders `RiskLevel` but never invents a score |
| Blockchain ingestion | IMPLEMENTED (live) | Wire to `GET /api/v1/health` + transfers endpoint |

Every synthetic record is flagged `isDemo: true` and surfaced with a visible
`DEMO DATA` badge plus the persistent demo banner. Nothing in demo mode is
presented as real intelligence.

## Run

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api -> 127.0.0.1:8000)
```

PowerShell quirk: `npm.ps1` may be blocked by the execution policy — use `npm.cmd`.

### Try the workflow

1. Sign in with any demo account (password `cryptotrace-demo`): `admin`,
   `investigator`, `analyst`, `reviewer`, or `readonly`.
2. **Wallets** → open a demo wallet (or paste any `0x…40hex` address) → see
   normalized transfers with the live API or the labeled demo fallback.
3. **Dashboard** → KPIs, risk chart, investigation activity, system status.
4. **Graph / VASP / Evidence / Reports** → labeled synthetic builders.

Role differences can be tested by logging in as `readonly` or `reviewer`
(limited actions).

## Scripts

| Script | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server with `/api` proxy |
| `npm run typecheck` | `tsc` (strict) |
| `npm run lint` | ESLint flat config, zero warnings allowed |
| `npm test` | Vitest (jsdom) |
| `npm run build` | `tsc --noEmit && vite build` |

## Architecture

```
src/
  api/        typed adapters + contracts (wallets, investigations, graph,
              attribution, evidence, reports), fetch client, data-source config
  auth/       AuthContext (demo session), permissions matrix, ProtectedRoute
  app/        DataSourceProvider (live/demo negotiation via /api/v1/health)
  components/ layout (shell, sidebar, topbar, search), ui library, feature blocks
              (transfers, investigations, graph, attribution, evidence, reports)
  features/   route pages, one folder per feature
  hooks/      useApi (async data with loading/error/reload)
  lib/        format/address/logger utilities (secret-safe)
  mock/       labeled synthetic data (transfers, cases, activity, graph,
              attribution, evidence, users)
  styles/     tokens + base + layout + components + print styles
  tests/      vitest setup + test suites
```

### Data-source mode

`src/api/config.ts` holds a module-level `live | demo` switch. On boot the
`DataSourceProvider` probes `GET /api/v1/health`; reachable ⇒ `live`, otherwise
`demo`. Manual override on the System Settings page. Adapt to whatever
representational contract each backend member publishes — every synthetic branch
is isolated behind a labeled adapter.

## Security posture

- No API keys or secrets in the frontend. The Vite proxy keeps the backend's
  Alchemy key server-side; production deployments must keep `/api` proxied
  server-side.
- Inputs reject secret material (seed phrases, private keys) and only accept
  public `0x` addresses.
- Errors are normalized user-safe strings with no stack/internal details
  (`src/api/client.ts`).
- Attribution UI uses "candidate / potential association" language and never
  claims verified ownership.
- RBAC in the UI is a convenience guard; the backend must remain the
  authorization authority.

## API contract used (Member 1)

See `docs/API_CONTRACTS.md` for the exact normalized transfer schema consumed by
`src/api/types.ts#BlockchainTransfer`.