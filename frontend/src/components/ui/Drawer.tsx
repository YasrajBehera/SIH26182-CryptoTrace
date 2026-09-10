import { useEffect } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  labelledBy?: string;
}

export function Drawer({ open, onClose, title, children, footer, wide, labelledBy }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  const labelId = labelledBy ?? "drawer-title";

  return createPortal(
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden />
      <aside
        className={`drawer ${wide ? "drawer-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelId}
      >
        <header className="drawer-header">
          <h3 id={labelId}>{title}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close panel">
            Esc
          </button>
        </header>
        <div className="drawer-body">{children}</div>
        {footer ? <footer className="drawer-footer">{footer}</footer> : null}
      </aside>
    </>,
    document.body,
  );
}