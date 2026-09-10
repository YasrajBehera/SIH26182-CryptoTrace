import type { CSSProperties, ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  glass?: boolean;
  bodyClassName?: string;
  style?: CSSProperties;
  "data-testid"?: string;
  id?: string;
}

export function Card({ title, subtitle, actions, children, className = "", glass, bodyClassName = "", style, "data-testid": testId, id }: CardProps) {
  return (
    <section id={id} className={`card ${glass ? "glass" : ""} ${className}`} style={style} data-testid={testId}>
      {title ? (
        <header className="card-header">
          <div>
            <h3 className="card-title">{title}</h3>
            {subtitle ? <p className="card-sub">{subtitle}</p> : null}
          </div>
          {actions ? <div className="row">{actions}</div> : null}
        </header>
      ) : null}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}