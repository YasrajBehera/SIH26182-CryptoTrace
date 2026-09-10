import { useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

interface BlockchainTransfer {
  transaction_hash: string;
  block_number: number | null;
  block_timestamp: string | null;
  from_address: string;
  to_address: string;
  value: string;
  asset: string;
  category: string;
  direction: string;
  raw_contract_address: string | null;
  raw_contract_value: string | null;
  chain: string;
}

interface PaginationInfo {
  max_transfers: number;
  fetched: number;
  truncated: boolean;
}

interface WalletTransfers {
  wallet_address: string;
  chain: string;
  transfers: BlockchainTransfer[];
  pagination: PaginationInfo;
}

interface BFSNode {
  wallet_id: string;
  address: string;
  chain: string;
  depth: number;
}

interface BFSResponse {
  wallet_id: string;
  max_depth: number;
  nodes: BFSNode[];
}

function isWalletTransfers(data: unknown): data is WalletTransfers {
  return (
    typeof data === "object" &&
    data !== null &&
    "wallet_address" in data &&
    "chain" in data &&
    "transfers" in data &&
    "pagination" in data
  );
}

function isBFSResponse(data: unknown): data is BFSResponse {
  return (
    typeof data === "object" &&
    data !== null &&
    "wallet_id" in data &&
    "max_depth" in data &&
    "nodes" in data
  );
}

function truncateAddress(addr: string): string {
  if (addr.length <= 16) return addr;
  return `${addr.slice(0, 8)}...${addr.slice(-6)}`;
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return "--";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

const DEPTH_COLORS = [
  "#1a73e8",
  "#e8710a",
  "#d93025",
  "#188038",
  "#9334e6",
  "#e37400",
  "#185abc",
];

function NetworkGraph({ data }: { data: BFSResponse }) {
  const width = 700;
  const height = 520;
  const cx = width / 2;
  const cy = height / 2;
  const nodes = data.nodes;

  const centerLabel = data.wallet_id.includes(":")
    ? data.wallet_id.split(":")[1]
    : data.wallet_id;

  if (nodes.length === 0) {
    return (
      <div className="graph-empty">
        <p>No neighbor nodes found in the graph for this wallet.</p>
      </div>
    );
  }

  const depthGroups = new Map<number, BFSNode[]>();
  for (const node of nodes) {
    const list = depthGroups.get(node.depth) ?? [];
    list.push(node);
    depthGroups.set(node.depth, list);
  }

  const ringSpacing = 80;
  const positions: { x: number; y: number }[] = [];

  for (const node of nodes) {
    const group = depthGroups.get(node.depth)!;
    const idx = group.indexOf(node);
    const groupCount = group.length;
    const ringRadius = node.depth * ringSpacing;
    const angle = (2 * Math.PI * idx) / groupCount - Math.PI / 2;
    positions.push({
      x: cx + ringRadius * Math.cos(angle),
      y: cy + ringRadius * Math.sin(angle),
    });
  }

  const maxRing = Math.max(...depthGroups.keys());
  const svgHeight = cy + maxRing * ringSpacing + 50;
  const viewBox = `0 0 ${width} ${svgHeight}`;

  return (
    <svg viewBox={viewBox} className="network-svg" role="img" aria-label="BFS network graph">
      {nodes.map((node, i) => (
        <line
          key={`edge-${node.wallet_id}`}
          x1={cx}
          y1={cy}
          x2={positions[i].x}
          y2={positions[i].y}
          stroke="#d0d5dd"
          strokeWidth={1.5}
        />
      ))}

      {nodes.map((node, i) => {
        const color = DEPTH_COLORS[node.depth % DEPTH_COLORS.length];
        return (
          <g key={node.wallet_id}>
            <circle
              cx={positions[i].x}
              cy={positions[i].y}
              r={7}
              fill={color}
              stroke="white"
              strokeWidth={2}
            />
            <text
              x={positions[i].x}
              y={positions[i].y + 18}
              textAnchor="middle"
              className="graph-node-label"
            >
              {truncateAddress(node.address)}
            </text>
            <text
              x={positions[i].x}
              y={positions[i].y + 29}
              textAnchor="middle"
              className="graph-depth-label"
            >
              d{node.depth}
            </text>
          </g>
        );
      })}

      <circle cx={cx} cy={cy} r={14} fill="#17202a" stroke="white" strokeWidth={3} />
      <text x={cx} y={cy + 26} textAnchor="middle" className="graph-center-label">
        {truncateAddress(centerLabel)}
      </text>
      <text x={cx} y={cy + 38} textAnchor="middle" className="graph-depth-label">
        queried
      </text>

      {[...depthGroups.keys()].sort((a, b) => a - b).map((d) => (
        <g key={`ring-${d}`}>
          <circle
            cx={cx}
            cy={cy}
            r={d * ringSpacing}
            fill="none"
            stroke="#eef1f4"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          <text
            x={cx + d * ringSpacing + 4}
            y={cy - 4}
            className="graph-depth-label"
          >
            depth {d}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default function App() {
  const [address, setAddress] = useState("");
  const [result, setResult] = useState<unknown>(null);
  const [graphData, setGraphData] = useState<BFSResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function investigate() {
    if (!address.trim()) return;

    setLoading(true);
    setResult(null);
    setGraphData(null);

    const walletAddr = address.trim();
    const walletId = `eth:${walletAddr}`;

    const transfersUrl = `${API_BASE}/api/v1/wallets/${walletAddr}/transfers`;
    const graphUrl = `${API_BASE}/api/v1/graph/wallets/${encodeURIComponent(walletId)}/bfs?depth=3&max_nodes=100`;

    try {
      const [txRes, graphRes] = await Promise.allSettled([
        fetch(transfersUrl),
        fetch(graphUrl),
      ]);

      if (txRes.status === "fulfilled" && txRes.value.ok) {
        setResult(await txRes.value.json());
      } else {
        setResult({ error: "Failed to fetch transfers." });
      }

      if (graphRes.status === "fulfilled" && graphRes.value.ok) {
        setGraphData(await graphRes.value.json());
      }
    } catch {
      setResult({ error: "Backend is not running." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <header>
        <p className="eyebrow">SIH26182</p>
        <h1>CryptoTrace</h1>
        <p className="subtitle">
          Explainable blockchain investigation & VASP attribution
        </p>
      </header>

      <section className="card">
        <label htmlFor="wallet">Suspicious wallet address</label>
        <div className="row">
          <input
            id="wallet"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Enter a public wallet address"
          />
          <button onClick={investigate} disabled={loading}>
            {loading ? "Analyzing..." : "Investigate"}
          </button>
        </div>
        <p className="hint">
          Only use lawful, public blockchain data. Never enter private keys or
          seed phrases.
        </p>
      </section>

      {isBFSResponse(graphData) && (
        <section className="card">
          <h2>Network Graph</h2>
          <div className="graph-meta">
            <span className="mono">{graphData.wallet_id}</span>
            <span>
              {graphData.nodes.length} node{graphData.nodes.length !== 1 && "s"} found
              {" "}(depth {graphData.max_depth})
            </span>
          </div>
          <NetworkGraph data={graphData} />
        </section>
      )}

      {isWalletTransfers(result) && (
        <section className="card dashboard">
          <h2>Transfer History</h2>

          <div className="summary-grid">
            <div className="summary-item">
              <span className="summary-label">Wallet</span>
              <span className="summary-value mono" title={result.wallet_address}>
                {truncateAddress(result.wallet_address)}
              </span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Chain</span>
              <span className="summary-value">{result.chain}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Total Transfers</span>
              <span className="summary-value">{result.pagination.fetched}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Max Requested</span>
              <span className="summary-value">{result.pagination.max_transfers}</span>
            </div>
          </div>

          {result.pagination.truncated && (
            <p className="truncated-notice">
              Results truncated — showing {result.pagination.fetched} of more
              available transfers.
            </p>
          )}

          {result.transfers.length === 0 ? (
            <p className="empty-state">No transfers found for this wallet.</p>
          ) : (
            <div className="transfer-table-wrap">
              <table className="transfer-table">
                <thead>
                  <tr>
                    <th>Direction</th>
                    <th>Asset</th>
                    <th>Value</th>
                    <th>From</th>
                    <th>To</th>
                    <th>Timestamp</th>
                    <th>Tx Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {result.transfers.map((t, i) => (
                    <tr key={`${t.transaction_hash}-${t.direction}-${i}`}>
                      <td>
                        <span className={`badge badge-${t.direction}`}>
                          {t.direction}
                        </span>
                      </td>
                      <td>{t.asset}</td>
                      <td className="mono">{t.value}</td>
                      <td className="mono" title={t.from_address}>
                        {truncateAddress(t.from_address)}
                      </td>
                      <td className="mono" title={t.to_address}>
                        {truncateAddress(t.to_address)}
                      </td>
                      <td>{formatTimestamp(t.block_timestamp)}</td>
                      <td className="mono" title={t.transaction_hash}>
                        {truncateAddress(t.transaction_hash)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {!!result && !isWalletTransfers(result) && (
        <section className="card">
          <h2>Response</h2>
          <pre>{JSON.stringify(result, null, 2) as string}</pre>
        </section>
      )}
    </main>
  );
}
