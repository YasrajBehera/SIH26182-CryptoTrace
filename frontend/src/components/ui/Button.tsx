import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "default" | "primary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  leading?: ReactNode;
  block?: boolean;
}

export function Button({
  variant = "default",
  size = "md",
  leading,
  block,
  className = "",
  children,
  type = "button",
  ...rest
}: BtnProps) {
  const classes = [
    "btn",
    variant !== "default" ? `btn-${variant}` : "",
    size !== "md" ? `btn-${size}` : "",
    block ? "btn-block" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type={type} className={classes} {...rest}>
      {leading}
      {children}
    </button>
  );
}