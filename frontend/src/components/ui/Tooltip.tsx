import { useState } from "react";
import type { ReactNode } from "react";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  wide?: boolean;
}

export function Tooltip({ content, children, wide }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  return (
    <span
      className="tooltip-wrap"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible ? (
        <span className={`tooltip ${wide ? "wide" : ""}`} role="tooltip">
          {content}
        </span>
      ) : null}
    </span>
  );
}