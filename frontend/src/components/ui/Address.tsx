import { useState } from "react";
import { ExplorerIcon } from "@/components/icons";
import { explorerLink, isLikelyAddress } from "@/lib/address";
import { shortenAddress } from "@/lib/format";
import { Tooltip } from "./Tooltip";

/**
 * Blockchain address display with copy + explorer link.
 * Only ever shows PUBLIC addresses. Never accepts secrets.
 */
export function Address({ address, chain = "eth", head = 6, tail = 4, silent }: { address: string; chain?: string; head?: number; tail?: number; silent?: boolean }) {
  const [copied, setCopied] = useState(false);
  const short = shortenAddress(address, head, tail);

  const copy = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(address);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = address;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  const valid = isLikelyAddress(address);

  return (
    <span className="address-inline" onClick={(e) => e.stopPropagation()}>
      <Tooltip content={valid ? address : "Address did not pass structural validation"} wide>
        <code className="address" data-testid="address-code">
          {short}
        </code>
      </Tooltip>
      <button
        className="btn btn-ghost btn-sm btn-icon"
        onClick={copy}
        aria-label={`Copy address ${address}`}
        title="Copy full address"
        style={{ width: 26, height: 26 }}
      >
        {copied ? <span className="copy-badge">✓</span> : <CopyIcon />}
      </button>
      {!silent && valid ? (
        <a
          className="btn btn-ghost btn-sm btn-icon"
          href={explorerLink(address, chain)}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open in explorer (opens in new tab)"
          title="Open in explorer"
          style={{ width: 26, height: 26 }}
        >
          <ExplorerIcon />
        </a>
      ) : null}
    </span>
  );
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13" aria-hidden>
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

/** Plain (non-interactive) truncated address, e.g. inside dense tables. */
export function ShortAddress({ address }: { address: string }) {
  return <code className="mono" style={{ color: "var(--cyan)" }}>{shortenAddress(address)}</code>;
}