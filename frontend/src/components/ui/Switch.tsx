interface SwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  size?: "sm" | "md";
}

export function Switch({ checked, onChange, label }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className={`switch ${checked ? "on" : ""}`}
      onClick={() => onChange(!checked)}
    />
  );
}