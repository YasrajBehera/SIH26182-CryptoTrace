import { Link } from "react-router-dom";
import { PageHeader, Button, Card } from "@/components/ui";

export function NotFoundPage() {
  return (
    <div className="page">
      <PageHeader title="Page not found" crumbs={[{ label: "404" }]} />
      <Card>
        <p style={{ color: "var(--text-muted)" }}>
          The page you requested does not exist or your role cannot access it. If you typed an address, check that
          it is a full public wallet address.
        </p>
        <div className="row" style={{ gap: 8 }}>
          <Link to="/dashboard" className="btn btn-primary">
            Go to overview
          </Link>
          <Button variant="ghost" onClick={() => window.history.back()}>
            Go back
          </Button>
        </div>
      </Card>
    </div>
  );
}