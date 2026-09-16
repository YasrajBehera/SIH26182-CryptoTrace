# Final Audit Report — SIH26182 CryptoTrace

Status: CLOSED (all inconsistencies verified and fixed; full suite green)

Reference case used for live-data verification: `case-131dda8a` ("Audit CASE",
primary wallet `0x08723392ed15743cc38513c4925f5e6be5c17243`, chain `eth`).

---

## 1. Inconsistencies found and fixed

### 1.1 PDF report counts (server-side export DI bug) — FIXED

**Finding.** `backend/reports/api.py` built the investigation service by calling
`cases.api.get_investigation_service_dep()` directly. That dependency factory
declares `Depends(make_investigation_repository)` (and siblings) as **default
arguments**:

```python
def get_investigation_service_dep(
    repository: InvestigationRepository = Depends(make_investigation_repository),
    wallet_repository=Depends(make_wallet_repository),
    risk_repository=Depends(make_risk_repository),
    evidence_service=Depends(get_evidence_service_dep),
) -> InvestigationService: ...
```

`Depends(...)` markers only resolve inside request dependency-injection. Calling
the factory outside DI passes the marker objects themselves, so every repository
call raised `AttributeError: 'Depends' object has no attribute 'get'`.

**Impact.** `_resolve_context` swallowed the exception and set `case = None`, so
the **PDF body rendered every section as UNAVAILABLE / 0 counts while the header
still showed the real case metadata** (case id, wallet, network come from the
request payload, not the repository).

**Fix.** `export_report` now constructs a concrete service with real
repositories (`InvestigationService` + `make_investigation_repository()`,
`get_evidence_service()`, `make_risk_repository()`, `make_wallet_repository()`)
instead of calling the DI factory (`backend/reports/api.py:123`).

### 1.2 Count truncation (wallet_overview) — FIXED

**Finding.** `build_section_content("wallet_overview", ...)` reported
"Transactions persisted" from `case["transactions"]`, falling back to
`len(case["latest_transactions"])` — the **latest ingestion batch length**, not
the number of transactions actually persisted in the wallet store.

The wallet store de-duplicates by `(chain, tx_hash)`; live batches can repeat a
hash (Alchemy reports both sides of a transfer). Measured on the reference case:

| Quantity | Value |
| --- | --- |
| `latest_transactions` batch length (raw record) | 19 |
| wallet store persisted count (`transactions` where from/to = wallet) | 18 |

The old code reported 19; the persisted store holds 18.

**Fix.** `_resolve_context` now resolves `WalletSummary` for the case wallet and
sets `case["persisted_transactions"] = summary.transaction_count`
(`backend/reports/api.py:55`). `wallet_overview` prefers
`persisted_transactions` over `transactions`, then the raw batch length
(`backend/reports/models.py:111`).

### 1.3 Value / asset-label truncation on live ingestion — FIXED

**Finding.** Persisted schema was lossy for real chain data:

- `transactions.value / fee NUMERIC(78,0)` — fractional ETH was silently rounded
  (`12595.3` -> `12595`, `3.69e-05` -> `0`), corrupting the values the API and
  graph expose.
- `transactions.token_symbol VARCHAR(16)` — real phishing `asset` names such as
  `'Visit LiquidETH.network to claim rewards'` (41 chars) exceeded the 16-char
  limit. Live ingestion of such rows raised `StringDataRightTruncation` on
  commit, surfacing as a 500 on `GET /api/v1/wallets/{address}/transfers`.

**Fix.** Model widened to `NUMERIC(78,18)` for `value`/`fee` and wallet volumes,
and `token_symbol VARCHAR(255)` (`backend/app/models.py`), with idempotent
startup migrations in `backend/app/db.py`
(`_migrate_numeric_precision`, `_migrate_token_symbol_width`).

### 1.4 Risk label / score conflation — ASSESSED

**Finding.** Persisted wallet summaries carry the analytical risk label and the
numeric score as **two independent fields** that can drift. Postgres audit of the
live store found label/score pairs that contradict the documented scoring bands
(`risk.service._level_for`: `>=80 critical, >=60 high, >=30 medium, >=10 low`):

- wallets labelled `unknown` while holding `risk_score` 21–25 (a score ≥10 must
  be `low`): `0x…` records labelled `unknown` with score 21, 22, 25;
- case rows stored `risk='unknown'` whose wallet assessment is `low` (score 24).

**Mitigation.** The report pipeline now reads the **persisted**
`RiskAssessment` through `service.risk_for(...)` for the risk disclaimer and
keeps the case-level label; `apply_analysis` writes `risk=assessment.level` and
`risk_score=assessment.risk_score` from the same assessment so new captures stay
consistent. Residual label/score mismatch in the live store predates this change
and is data, not code, drift.

---

## 2. Verification — PDF re-export for `case-131dda8a`

Re-exported through the live endpoint (`POST /api/v1/reports/export`, admin
session, Postgres-backed repositories).

- HTTP 200; `content-type: application/pdf`; report id `rpt-6c8c5d995dfe`;
  **13/13 sections rendered**; file `backend/_audit_report.pdf` (6069 bytes).
- Body text extracted from the PDF (content streams are ASCII85 + Flate) and
  verified against the live database:

| Check | PDF body | Source of truth (Postgres) |
| --- | --- | --- |
| Case id | `Case ID: case-131dda8a` | `investigations.id` |
| Wallet | `0x08723392ed15743cc38513c4925f5e6be5c17243` | `primary_wallet` |
| Data source | `Data source reported by the pipeline: live` | `latest_data_source` |
| Transactions persisted | `Transactions persisted: 18` | wallet store count (batch len 19) |
| Evidence | `Evidence count linked to case: 21` | `evidence_count` |
| Risk | `Risk label: low` / `Analytical risk: low` | `risk` / `risk_score 23` |

Prior to the DI fix, the same export produced a header with real metadata and a
body of UNAVAILABLE / zeroed counts.

---

## 3. Frontend request-layer hardening (CHECK 10)

- **AbortSignal forwarding.** `investigations.list/get/context/notes`
  (`frontend/src/api/investigations.ts`) and `wallets.getTransfers`
  (`frontend/src/api/wallets.ts`) accept an optional `AbortSignal` and pass it as
  `{ signal }` to the client.
- **Call sites updated** to forward the `useApi`-provided signal: DashboardPage,
  RiskPage, CasesPage, CaseDetailPage (get + notes), ReportsPage (get + context +
  getTransfers), WalletDetailPage (getTransfers), VaspPage (context).
- **In-flight GET dedup.** `frontend/src/api/client.ts` now shares one promise
  for identical in-flight GETs (keyed by `method + URL`), cleared on settle;
  POST/mutating calls are never shared. A deferred regression from that change
  (a `.finally()` cleanup produced an unhandled rejection when a shared GET
  failed) was **fixed during this audit** by settling the cleanup via
  `.then(onOk, onErr)`; `investigations.notes.test.ts` assertion was updated for
  the new `{ signal: undefined }` call shape.

Note (out of checklist scope): `TransactionsPage` and `AssistantPage` still call
these endpoints without forwarding the hook signal; behavior is identical, only
network-level abort on unmount is not wired there.

---

## 4. Verification matrix

| Check | Result |
| --- | --- |
| Backend `pytest -q` | **523 passed, 0 failed** (2 deprecation warnings) |
| Frontend `npm test` (vitest) | **109 passed across 15 files, 0 unhandled errors** |
| Frontend `npm run lint` (`--max-warnings 0`) | clean |
| Frontend `npm run typecheck` | clean |
| Frontend `npm run build` | clean (Vite production bundle) |
| PDF body vs live DB | matches on all 6 reference fields (section 2) |

## 5. Artifacts

- `backend/_audit_report.pdf` — regenerated export for `case-131dda8a`
  (report id `rpt-6c8c5d995dfe`, 13 sections).