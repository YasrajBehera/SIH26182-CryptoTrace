import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SearchIcon } from "@/components/icons";
import { investigations } from "@/api/investigations";
import { getDemoEvidence } from "@/mock";
import { shortenAddress } from "@/lib/format";
import { isLikelyAddress, isLikelyHash } from "@/lib/address";

interface SearchResultGroup {
  category: string;
  results: Array<{
    id: string;
    label: string;
    meta: string;
    to: string;
  }>;
}

/** Global search across wallets, cases, entities, evidence, transactions. */
export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [caseList, setCaseList] = useState<Awaited<ReturnType<typeof investigations.list>>>([]);
  const [evidenceList] = useState(() => getDemoEvidence());

  useEffect(() => {
    let cancelled = false;
    investigations.list().then((c) => {
      if (!cancelled) setCaseList(c);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // "/" keyboard shortcut focuses search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (e.key === "/" && target.tagName !== "INPUT" && target.tagName !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const groups = useMemo<SearchResultGroup[]>(() => {
    const q = query.trim().toLowerCase();
    if (q.length < 2) return [];
    const out: SearchResultGroup[] = [];

    if (isLikelyAddress(q)) {
      out.push({
        category: "Wallets",
        results: [
          { id: q, label: q, meta: "Wallet", to: `/wallets/${q}` },
          { id: `${q}-g`, label: `${q} (graph)`, meta: "Graph", to: `/graph?address=${encodeURIComponent(q)}` },
        ],
      });
    }

    if (isLikelyHash(q)) {
      out.push({
        category: "Transactions",
        results: [
          { id: q, label: q, meta: "Transaction", to: `/transactions?hash=${encodeURIComponent(q)}` },
        ],
      });
    }

    const matchingCases = caseList.filter((c) => {
      const hay = `${c.id} ${c.name} ${c.primaryWallet} ${c.tags.join(" ")} ${c.assignedAnalyst}`.toLowerCase();
      return hay.includes(q);
    });
    if (matchingCases.length) {
      out.push({
        category: "Cases",
        results: matchingCases.slice(0, 6).map((c) => ({
          id: c.id,
          label: `${c.id} — ${c.name}`,
          meta: c.primaryWallet,
          to: `/cases/${c.id}`,
        })),
      });
    }

    const matchingEvidence = evidenceList.filter((e) => {
      const hay = `${e.id} ${e.title} ${e.source} ${e.relatedWallet ?? ""}`.toLowerCase();
      return hay.includes(q) || q === e.id.toLowerCase();
    });
    if (matchingEvidence.length) {
      out.push({
        category: "Evidence",
        results: matchingEvidence.slice(0, 4).map((e) => ({
          id: e.id,
          label: `${e.id} — ${e.title}`,
          meta: e.type,
          to: `/evidence?focus=${e.id}`,
        })),
      });
    }

    // VASP entity name search (demo candidates are the only "entities" today)
    if (q.includes("staking") || q.includes("exchange") || q.includes("candidate")) {
      out.push({
        category: "Entities",
        results: [
          {
            id: "cand-1",
            label: "StakingPool.io (candidate)",
            meta: "VASP candidate",
            to: `/vasp?focus=cand-1`,
          },
        ],
      });
    }

    return out;
  }, [query, caseList, evidenceList]);

  const flatResults = groups.flatMap((g) => g.results);

  useEffect(() => setActive(0), [query]);

  const selectResult = (to: string) => {
    setOpen(false);
    setQuery("");
    navigate(to);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!groups.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, flatResults.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = flatResults[active];
      if (hit) selectResult(hit.to);
    }
  };

  let resultIndex = -1;

  return (
    <div className="global-search">
      <SearchIcon />
      <input
        ref={inputRef}
        className="input"
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-label="Global search"
        placeholder="Search wallets, transactions, cases, evidence…"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
      />
      <kbd aria-hidden>/</kbd>
      {open && groups.length ? (
        <div className="global-search-results" role="listbox">
          {groups.map((g) => (
            <div key={g.category}>
              <div className="search-result-group">{g.category}</div>
              {g.results.map((r) => {
                resultIndex += 1;
                return (
                  <div
                    key={`${g.category}-${r.id}`}
                    role="option"
                    aria-selected={resultIndex === active}
                    className={`search-result-row ${resultIndex === active ? "highlighted" : ""}`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectResult(r.to);
                    }}
                  >
                    <span className="mono" style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {shortenAddress(r.label, 12, 6)}
                    </span>
                    <span className="result-meta">{r.meta}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}