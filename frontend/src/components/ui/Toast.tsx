import { useToast } from "./ToastProvider";

const KIND_ICON: Record<string, string> = {
  ok: "✓",
  error: "✕",
  info: "ℹ",
  warn: "!",
};

export function ToastStack() {
  const { toasts, dismiss } = useToast();
  if (!toasts.length) return null;
  return (
    <div className="toast-stack" role="region" aria-label="Notifications" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`} role="status">
          <span aria-hidden>{KIND_ICON[t.kind]}</span>
          <div>
            <div className="toast-title">{t.title}</div>
            {t.description ? <div className="toast-desc">{t.description}</div> : null}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}