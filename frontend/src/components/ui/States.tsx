import type { ReactNode } from "react";

interface StateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
}

function StateShell({ title, description, icon, action }: StateProps) {
  return (
    <div className="state" role="status">
      {icon ? <div className="state-icon">{icon}</div> : null}
      <p className="state-title">{title}</p>
      {description ? <p className="state-desc">{description}</p> : null}
      {action ? <div className="row" style={{ marginTop: 8 }}>{action}</div> : null}
    </div>
  );
}

export function EmptyState(props: StateProps) {
  return <StateShell title={props.title} description={props.description} icon={props.icon ?? "◌"} action={props.action} />;
}

export function ErrorState({
  title = "Something went wrong",
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <StateShell
      title={title}
      description={
        description ??
        "The data could not be loaded. This is a service-level error — no internal details are shown."
      }
      icon="⚠"
      action={action}
    />
  );
}

export function UnauthorizedState({ action }: { action?: ReactNode }) {
  return (
    <StateShell
      title="Authorization required"
      description="Your account does not have permission to view this resource."
      icon="🔒"
      action={action}
    />
  );
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state" role="status">
      <span className="inline-spinner" aria-hidden />
      <p className="state-desc">{label}</p>
    </div>
  );
}

export function InlineSpinner() {
  return <span className="inline-spinner" role="status" aria-label="Loading" />;
}