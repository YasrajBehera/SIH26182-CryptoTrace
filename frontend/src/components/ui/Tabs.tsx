import type { ReactNode } from "react";

export interface TabItem {
  key: string;
  label: ReactNode;
  count?: number;
}

export function Tabs({
  tabs,
  active,
  onChange,
  id,
}: {
  tabs: TabItem[];
  active: string;
  onChange: (key: string) => void;
  id?: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label="Sections">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          id={id ? `${id}-${t.key}` : undefined}
          aria-selected={active === t.key}
          className={`tab ${active === t.key ? "active" : ""}`}
          onClick={() => onChange(t.key)}
        >
          {t.label}
          {t.count !== undefined ? <span className="tab-count">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}