import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export interface Crumb {
  label: ReactNode;
  to?: string;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      {items.map((c, i) => (
        <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          {c.to ? <Link to={c.to}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
          {i < items.length - 1 ? <span className="sep" aria-hidden>›</span> : null}
        </span>
      ))}
    </nav>
  );
}

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  crumbs?: Crumb[];
}

export function PageHeader({ title, subtitle, actions, crumbs }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div>
        {crumbs && crumbs.length ? <Breadcrumbs items={crumbs} /> : null}
        <h1>{title}</h1>
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
    </header>
  );
}