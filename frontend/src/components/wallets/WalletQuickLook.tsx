import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input, Button, Field } from "@/components/ui";
import { validateAddressInput, containsSecretMaterial } from "@/lib/address";
import { useToast } from "@/components/ui";

export function WalletQuickLook() {
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { push } = useToast();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (containsSecretMaterial(address)) {
      setError("Private keys and seed phrases are never accepted. Only public addresses.");
      return;
    }
    const problem = validateAddressInput(address);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    push({ kind: "info", title: "Opening wallet analysis", description: "Loading transfers for the supplied address." });
    navigate(`/wallets/${encodeURIComponent(address.trim())}`);
  };

  return (
    <form className="stack" onSubmit={submit} data-testid="wallet-quick-look">
      <Field
        label="Public wallet address"
        htmlFor="quick-look-address"
        hint="Only public, lawful blockchain data is processed. Secret material is rejected."
        error={error}
      >
        <div className="input-group">
          <Input
            id="quick-look-address"
            className="mono"
            placeholder="0x… (only public addresses)"
            value={address}
            invalid={!!error}
            onChange={(e) => {
              setAddress(e.target.value);
              setError(null);
            }}
            aria-describedby="quick-look-hint"
          />
          <Button variant="primary" type="submit">
            Open
          </Button>
        </div>
      </Field>
    </form>
  );
}