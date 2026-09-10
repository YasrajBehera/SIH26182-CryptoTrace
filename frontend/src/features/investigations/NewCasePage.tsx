import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader, Button, Card, Field, Input, Select, Textarea, DemoBadge, Badge } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/ui";
import { investigations } from "@/api/investigations";
import { validateAddressInput } from "@/lib/address";

export function NewCasePage() {
  const navigate = useNavigate();
  const { can, user } = useAuth();
  const { push } = useToast();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [wallet, setWallet] = useState("");
  const [network, setNetwork] = useState("Ethereum");
  const [priority, setPriority] = useState("medium");
  const [saving, setSaving] = useState(false);

  if (!can("investigation.create")) {
    return (
      <div className="page">
        <PageHeader title="New Investigation" />
        <Card>
          <p style={{ color: "var(--text-muted)" }}>
            Your role does not permit creating investigations. Ask an administrator or investigator for access.
          </p>
        </Card>
      </div>
    );
  }

  const addressProblem = wallet ? validateAddressInput(wallet) : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (addressProblem) return;
    setSaving(true);
    try {
      const created = await investigations.create({
        name,
        description,
        primaryWallet: wallet.trim(),
        network,
        priority,
        tags: ["crime-finance", "typology-review"],
      });
      push({ kind: "ok", title: "Investigation created", description: `${created.id} (demo persistence)` });
      navigate(`/cases/${created.id}`);
    } catch (err) {
      push({ kind: "error", title: "Could not create investigation", description: err instanceof Error ? err.message : "Unexpected error" });
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="New Investigation"
        subtitle="Create a case shell. Persistence is mocked until the backend ships a case store."
        crumbs={[{ label: "Investigations", to: "/investigations" }, { label: "New" }]}
      />

      <Card title="Case details">
        <DemoBadge />
        <form className="stack" onSubmit={submit}>
          <Field label="Case name" htmlFor="nc-name" hint="Human-readable title, e.g. ‘Suspicious USDT migration — Chain A’">
            <Input id="nc-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </Field>
          <Field label="Description" htmlFor="nc-desc">
            <Textarea id="nc-desc" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What are you investigating?" />
          </Field>
          <div className="grid grid-2">
            <Field label="Primary wallet" htmlFor="nc-wallet" error={addressProblem ?? undefined}>
              <Input id="nc-wallet" className="mono" value={wallet} invalid={!!addressProblem} onChange={(e) => setWallet(e.target.value)} placeholder="0x…" required />
            </Field>
            <Field label="Network" htmlFor="nc-net">
              <Select id="nc-net" value={network} onChange={(e) => setNetwork(e.target.value)}>
                <option>Ethereum</option>
                <option>Polygon</option>
                <option>Arbitrum</option>
                <option>Optimism</option>
                <option>Base</option>
              </Select>
            </Field>
          </div>
          <Field label="Priority" htmlFor="nc-priority">
            <Select id="nc-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </Select>
          </Field>
          <div className="row" style={{ gap: 8 }}>
            <Button variant="primary" type="submit" disabled={saving || !name || !wallet || !!addressProblem}>
              {saving ? "Creating…" : "Create investigation"}
            </Button>
            <Button variant="ghost" type="button" onClick={() => navigate("/investigations")}>
              Cancel
            </Button>
            {user ? (
              <Badge className="status-open" style={{ marginLeft: "auto" }}>
                Creator: {user.name}
              </Badge>
            ) : null}
          </div>
        </form>
      </Card>
    </div>
  );
}