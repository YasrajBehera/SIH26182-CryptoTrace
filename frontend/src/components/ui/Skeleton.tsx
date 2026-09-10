export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function SkeletonTitle() {
  return <Skeleton className="sk-title" />;
}

export function SkeletonKpi() {
  return <Skeleton className="sk-kpi" />;
}

export function SkeletonBlock({ rows = 5 }: { rows?: number }) {
  return (
    <div className="stack" aria-hidden>
      <Skeleton className="sk-block" />
      <div className="stack" style={{ gap: 8 }}>
        {Array.from({ length: rows }, (_, i) => (
          <Skeleton key={i} className="sk-row" />
        ))}
      </div>
    </div>
  );
}