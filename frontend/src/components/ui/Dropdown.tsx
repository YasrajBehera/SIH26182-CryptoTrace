import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export interface DropdownItem {
  key: string;
  /** Separator rows use key "__sep" and may omit a label. */
  label?: ReactNode;
  icon?: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  danger?: boolean;
}

interface DropdownProps {
  trigger: ReactNode;
  items: DropdownItem[];
  label?: string;
}

export function Dropdown({ trigger, items, label }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", handler);
    window.addEventListener("keydown", keyHandler);
    return () => {
      window.removeEventListener("mousedown", handler);
      window.removeEventListener("keydown", keyHandler);
    };
  }, [open]);

  return (
    <div className="dropdown" ref={ref}>
      <button
        className="btn btn-ghost"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
      >
        {trigger}
      </button>
      {open ? (
        <div className="dropdown-menu" role="menu">
          {items.map((item) =>
            item.key === "__sep" ? (
              <div key={item.key} className="dropdown-sep" />
            ) : (
              <button
                key={item.key}
                role="menuitem"
                className={`dropdown-item ${item.danger ? "danger" : ""}`}
                disabled={item.disabled}
                onClick={() => {
                  setOpen(false);
                  item.onClick?.();
                }}
              >
                {item.icon}
                {item.label}
              </button>
            ),
          )}
        </div>
      ) : null}
    </div>
  );
}