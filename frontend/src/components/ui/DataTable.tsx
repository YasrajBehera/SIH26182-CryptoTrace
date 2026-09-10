import { useMemo, useState } from "react";
import type { ReactNode } from "react";

export type SortDirection = "asc" | "desc";

export interface ColumnDef<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number | null | undefined;
  align?: "left" | "right";
  hideBelow?: number;
}

interface DataTableProps<T> {
  rows: T[];
  columns: ColumnDef<T>[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  initialSort?: { key: string; dir: SortDirection };
  pagination?: { pageSize: number };
  footer?: ReactNode;
  testid?: string;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  onRowClick,
  empty,
  initialSort,
  pagination,
  footer,
  testid,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; dir: SortDirection } | null>(initialSort ?? null);
  const [page, setPage] = useState(1);

  const pageSize = pagination?.pageSize ?? 20;
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av === bv) return 0;
      if (av === null || av === undefined || av === "") return 1;
      if (bv === null || bv === undefined || bv === "") return -1;
      return av < bv ? -dir : dir;
    });
  }, [rows, sort, columns]);

  const pageRows = pagination ? sorted.slice((page - 1) * pageSize, page * pageSize) : sorted;

  const toggleSort = (col: ColumnDef<T>) => {
    if (!col.sortValue) return;
    setSort((prev) => {
      if (prev?.key === col.key) {
        return { key: col.key, dir: prev.dir === "asc" ? "desc" : "asc" };
      }
      return { key: col.key, dir: "asc" };
    });
  };

  return (
    <div>
      <div className="table-wrap" data-testid={testid}>
        <table className="data-table">
          <caption className="sr-only">Data table</caption>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`${c.sortValue ? "sortable" : ""} ${c.align === "right" ? "num" : ""}`}
                  onClick={c.sortValue ? () => toggleSort(c) : undefined}
                  onKeyDown={
                    c.sortValue
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            toggleSort(c);
                          }
                        }
                      : undefined
                  }
                  role={c.sortValue ? "button" : undefined}
                  tabIndex={c.sortValue ? 0 : undefined}
                  aria-sort={
                    sort?.key === c.key ? (sort.dir === "asc" ? "ascending" : "descending") : undefined
                  }
                  title={c.sortValue ? `Sort by ${typeof c.header === "string" ? c.header : "column"}` : undefined}
                >
                  {c.header}
                  {c.sortValue && sort?.key === c.key ? <span className="sort-ind">{sort.dir === "asc" ? "▲" : "▼"}</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length}>{empty ?? "No rows to display."}</td>
              </tr>
            ) : (
              pageRows.map((row) => (
                <tr
                  key={rowKey(row)}
                  className={onRowClick ? "clickable" : ""}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={c.align === "right" ? "num" : ""}>
                      {c.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {pagination || footer ? (
        <div className="table-footer">
          {footer ?? (
            <span>
              {rows.length} row{rows.length === 1 ? "" : "s"}
            </span>
          )}
          {pagination ? (
            <nav className="pagination" aria-label="Pagination">
              <button className="paginate-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                ‹
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                .map((p, idx, arr) => (
                  <span key={p} style={{ display: "inline-flex", gap: 2 }}>
                    {idx > 0 && arr[idx - 1] !== p - 1 ? <span className="paginate-btn" aria-hidden>…</span> : null}
                    <button
                      className={`paginate-btn ${p === page ? "active" : ""}`}
                      onClick={() => setPage(p)}
                      aria-current={p === page ? "page" : undefined}
                    >
                      {p}
                    </button>
                  </span>
                ))}
              <button className="paginate-btn" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                ›
              </button>
            </nav>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}