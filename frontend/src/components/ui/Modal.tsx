import { useEffect } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg";
  labelledBy?: string;
}

export function Modal({ open, onClose, title, children, footer, size = "md", labelledBy }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  const labelId = labelledBy ?? "modal-title";

  return createPortal(
    <div className="backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className={`modal ${size === "lg" ? "modal-lg" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelId}
      >
        <header className="modal-header">
          <h3 id={labelId}>{title}</h3>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close dialog">
            Esc
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer ? <footer className="modal-footer">{footer}</footer> : null}
      </div>
    </div>,
    document.body,
  );
}