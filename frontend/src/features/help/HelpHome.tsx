import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../../session";
import { useWorkspaces } from "../../workspaces";
import { Card, EmptyState, PageHeader, SearchInput, Skeleton } from "../../ui";
import { REFERENCE_SHELF, orderShelves, shelfFor, type Shelf } from "./shelves";
import { searchHelp } from "./search";
import type { HelpEntry, ShelfId } from "./types";

function PageList({ entries }: { entries: HelpEntry[] }) {
  return (
    <ul className="help-list">
      {entries.map((entry) => (
        <li key={entry.slug}>
          <Link to={`/help/${entry.slug}`}>{entry.title}</Link>
          <span className="help-list__summary">{entry.summary}</span>
        </li>
      ))}
    </ul>
  );
}

function ShelfCard({ shelf, entries }: { shelf: Shelf; entries: HelpEntry[] }) {
  return (
    <Card title={shelf.title}>
      <p className="help-shelf__audience">{shelf.audience}</p>
      {entries.length > 0 ? (
        <PageList entries={entries} />
      ) : (
        <p className="help-shelf__empty">No guides on this shelf yet.</p>
      )}
    </Card>
  );
}

/** The reader's own shelf, or null while their workspaces (and so their role) are loading. */
function useOwnShelf(): ShelfId | null {
  const { session } = useSession();
  const { workspaces, loading } = useWorkspaces();
  if (session?.user.is_admin) return "admin";
  // Choosing before the list arrives would show the member order and then reorder under the reader.
  if (loading) return null;
  return workspaces.some((workspace) => workspace.role === "steward") ? "stewards" : "using";
}

/** The help home page: search, then four shelves with the reader's own first (HP-02, HP-05). */
export function HelpHome({ entries }: { entries: HelpEntry[] }) {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const own = useOwnShelf();
  const results = searchHelp(entries, query);
  const onShelf = (shelf: Shelf) => entries.filter((entry) => shelfFor(entry) === shelf.id);

  return (
    <section className="help-home">
      <PageHeader
        title="Help"
        scope="Step-by-step guides for members, stewards, administrators and the person who looks after the server."
      />
      <SearchInput
        label="Search help"
        placeholder="Search help, for example password"
        initialValue={query}
        resultCount={query ? results.length : null}
        onSearch={(text) => setParams(text ? { q: text } : {}, { replace: true })}
      />
      {query ? (
        results.length > 0 ? (
          <PageList entries={results} />
        ) : (
          <EmptyState title="No guides match your search">
            Try a shorter word, or look through the shelves below by clearing the search.
          </EmptyState>
        )
      ) : (
        <div className="help-shelves">
          {entries.some((entry) => entry.slug === "whats-new") && (
            <p className="help-whats-new">
              <Link to="/help/whats-new">What is new in this release</Link>
            </p>
          )}
          {own === null ? (
            <Skeleton lines={6} label="Loading help shelves" />
          ) : (
            orderShelves(own).map((shelf) => (
              <ShelfCard key={shelf.id} shelf={shelf} entries={onShelf(shelf)} />
            ))
          )}
          <ShelfCard shelf={REFERENCE_SHELF} entries={onShelf(REFERENCE_SHELF)} />
        </div>
      )}
    </section>
  );
}
