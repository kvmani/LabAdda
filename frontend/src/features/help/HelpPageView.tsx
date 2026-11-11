import { Link, useNavigate, useParams } from "react-router-dom";
import { Breadcrumbs, Button, EmptyState, PageHeader } from "../../ui";
import { HelpArticle } from "./HelpArticle";
import { formatUpdated } from "./format";
import type { HelpEntry } from "./types";

/** One help page at /help/<shelf>/<page>, with a print button and its last-updated date. */
export function HelpPageView({ entries }: { entries: HelpEntry[] }) {
  const slug = useParams()["*"] ?? "";
  const navigate = useNavigate();
  const entry = entries.find((candidate) => candidate.slug === slug);
  if (!entry) {
    return (
      <EmptyState
        title="That help page does not exist"
        action={<Link to="/help">Go to the help home page</Link>}
      >
        It may have been renamed. Search the help home page for what you need.
      </EmptyState>
    );
  }
  return (
    <section className="help-page">
      <div className="help-noprint">
        <Breadcrumbs items={[{ label: "Help", to: "/help" }, { label: entry.title }]} />
      </div>
      <PageHeader
        title={entry.title}
        scope={entry.summary}
        action={
          <span className="help-noprint">
            <Button onClick={() => window.print()}>Print this page</Button>
          </span>
        }
      />
      <HelpArticle slug={entry.slug} onOpenPage={(page) => navigate(`/help/${page}`)} />
      <p className="help-updated">Last updated {formatUpdated(entry.updated)}</p>
    </section>
  );
}
