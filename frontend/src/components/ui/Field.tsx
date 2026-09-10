import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes, SelectHTMLAttributes } from "react";

interface FieldProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
  className?: string;
}

export function Field({ label, hint, error, children, htmlFor, className = "" }: FieldProps) {
  return (
    <div className={`field ${className}`}>
      {label ? <label htmlFor={htmlFor}>{label}</label> : null}
      {children}
      {hint ? <div className="field-hint">{hint}</div> : null}
      {error ? <div className="field-error" role="alert">{error}</div> : null}
    </div>
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export function Input({ invalid, className = "", ...rest }: InputProps) {
  const classes = ["input", invalid ? "has-error" : "", className].filter(Boolean).join(" ");
  return <input className={classes} {...rest} />;
}

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ className = "", ...rest }: TextareaProps) {
  return <textarea className={`input ${className}`} {...rest} />;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options?: ReadonlyArray<{ value: string; label: string }>;
  placeholder?: string;
}

export function Select({ options = [], placeholder, children, className = "", ...rest }: SelectProps) {
  return (
    <select className={`input ${className}`} {...rest}>
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
      {children}
    </select>
  );
}