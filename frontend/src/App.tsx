import { useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

export default function App() {
  const [address, setAddress] = useState("");
  const [result, setResult] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  async function investigate() {
    if (!address.trim()) return;

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/api/v1/investigations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address: address.trim() }),
      });

      const data = await response.json();
      setResult(data);
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
          Only use lawful, public blockchain data. Never enter private keys or seed phrases.
        </p>
      </section>

      {result && (
        <section className="card">
          <h2>Investigation response</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      )}
    </main>
  );
}
