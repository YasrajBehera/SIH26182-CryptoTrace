import { useState } from "react";
import { Link } from "react-router-dom";
import {
  PageHeader,
  Card,
  Button,
  Input,
  Badge,
  EmptyState,
  DemoBadge,
  LoadingBlock,
  UnauthorizedState,
} from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { globalSearch } from "@/api/search";
import { useDataSource } from "@/app/DataSourceContext";
import { useAuth } from "@/auth/AuthContext";
import type { SearchEntityType, SearchResult } from "@/api/types";

const TYPE_LABELS: Record<SearchEntityType, string> = {
  investigation: "Investigation",
  wallet: "Wallet",
  transaction: "Transaction",
  evidence: "Evidence",
  attribution: "Analysis",
  vasp: "VASP",
  report: "Report",
};

const TYPE_ORDER: SearchEntityType[] = [
  "investigation",
  "wallet",
  "transaction",
  "evidence",
  "attribution",
  "vasp",
  "report",
];

export function SearchPage() {
  const { isDemo } = useDataSource();
  const { can } = useAuth();
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [entityType, setEntityType] = useState<SearchEntityType | "all">("all");

  const { data, loading, error, reload } = useApi<SearchResult[] | null>(
    () =>
      submitted.length >= 2
        ? globalSearch
            .search(submitted, entityType === "all" ? undefined : entityType)
            .then((res) => res.results)
        : Promise.resolve(null),
    [submitted, entityType],
  );

  if (!can("search.read")) {
    return (
      <div className="page">
        <PageHeader title="Global Search" />
        <UnauthorizedState />
      </div>
    );
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    setSubmitted(query.trim());
  };

  const groups = TYPE_ORDER.map((t) => ({
    type: t,
    label: TYPE_LABELS[t],
    results: (data ?? []).filter((r) => r.entity_type === t),
  })).filter((g) => g.results.length > 0);

  return (
    <div className="page">
      <PageHeader
        title="Global Search"
        subtitle="Find investigations, wallets, transactions, evidence, analyses, curated VASPs, and reports across the platform."
        crumbs={[{ label: "Search" }]}
        actions={
          isDemo ? (
            <DemoBadge label="DEMO - SYNTHETIC RESULTS" />
          ) : (
            <Badge className="status-open">LIVE - BACKEND SEARCH</Badge>
          )
        }
      />

      <Card title="Search terms" subtitle="Search is case-insensitive and matches entity identifiers, names, addresses, and hashes.">
        <form className="stack" onSubmit={submit}>
          <div className="input-group">
            <Input
              aria-label="Search term"
              className="mono"
              placeholder="Case id, wallet address, tx hash, or VASP name..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Button type="submit" variant="primary">
              Search
            </Button>
          </div>
          <div className="filter-chips" role="group" aria-label="Filter by entity type">
            {(["all", ...TYPE_ORDER] as const).map((t) => (
              <button
                key={t}
                type="button"
                className={`chip ${entityType === t ? "active" : ""}`}
                onClick={() => setEntityType(t)}
              >
                {t === "all" ? "All types" : TYPE_LABELS[t]}
              </button>
            ))}
          </div>
        </form>
      </Card>

      {submitted && loading ? (
        <LoadingBlock />
      ) : error ? (
        <Card>
          <p style={{ color: "var(--text-muted)" }}>{error}</p>
          <Button onClick={reload}>Retry</Button>
        </Card>
      ) : submitted && !groups.length ? (
        <EmptyState
          title="No matches"
          description={
            isDemo
              ? "The synthetic search index returned nothing for this term. Try a case id, wallet address, or VASP name from the demo datasets."
              : "No data-grounded records matched this term in the backend search index."
          }
        />
      ) : groups.length ? (
        <div className="stack">
          {groups.map((g) => (
            <Card key={g.type} title={g.label} subtitle={`${g.results.length} match${g.results.length === 1 ? "" : "es"}`}>
              <div className="search-results">
                {g.results.map((r) => (
                  <SearchResultRow key={`${r.entity_type}:${r.id}`} result={r} />
                ))}
              </div>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SearchResultRow({ result }: { result: SearchResult }) {
  return (
    <Link className="search-result" to={result.url || "#"} data-testid="search-result">
      <div className="search-result-title">
        <Badge className="status-open" style={{ textTransform: "uppercase" }}>
          {TYPE_LABELS[result.entity_type]}
        </Badge>
        <span className="mono" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {result.title}
        </span>
      </div>
      {result.subtitle ? <div className="search-result-subtitle">{result.subtitle}</div> : null}
    </Link>
  );
}