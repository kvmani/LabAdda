import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Skeleton } from "../../ui";
import { useWorkspaces } from "../../workspaces";
export function HomeSpacesCard() {
  const { workspaces, loading: workspacesLoading } = useWorkspaces();
  const [spaceFilter, setSpaceFilter] = useState<"all" | "org" | "project" | "group">("all");
  const [spaceSearch, setSpaceSearch] = useState("");

  // Filtered workspaces
  const filteredWorkspaces = useMemo(() => {
    return workspaces.filter((ws) => {
      if (spaceFilter !== "all" && ws.kind !== spaceFilter) return false;
      if (spaceSearch.trim()) {
        const query = spaceSearch.toLowerCase();
        return ws.name.toLowerCase().includes(query) || (ws.description || "").toLowerCase().includes(query);
      }
      return true;
    });
  }, [workspaces, spaceFilter, spaceSearch]);

  const orgCount = workspaces.filter((w) => w.kind === "org").length;
  const projectCount = workspaces.filter((w) => w.kind === "project").length;
  const groupCount = workspaces.filter((w) => w.kind === "group").length;
  return (
    <section id="workspaces" className="wb-card" aria-label="Your team workspaces">
      <div className="wb-card__header">
        <div>
          <h2 className="wb-card__title">
            <span className="wb-card__icon" aria-hidden="true">
              🏢
            </span>
            <span>Your Team Spaces</span>
          </h2>
          <p className="wb-card__subtitle">Divisions, sections, projects & groups</p>
        </div>
        <Link to="/groups/new" className="wb-card__link">
          + New group
        </Link>
      </div>

      <div className="wb-card__body">
        {/* Space category filters */}
        <div className="wb-space-filters" role="tablist" aria-label="Workspace filters">
          <button
            type="button"
            role="tab"
            aria-selected={spaceFilter === "all"}
            className={`wb-space-filter-btn ${spaceFilter === "all" ? "wb-space-filter-btn--active" : ""}`}
            onClick={() => setSpaceFilter("all")}
          >
            All ({workspaces.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={spaceFilter === "org"}
            className={`wb-space-filter-btn ${spaceFilter === "org" ? "wb-space-filter-btn--active" : ""}`}
            onClick={() => setSpaceFilter("org")}
          >
            Units ({orgCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={spaceFilter === "project"}
            className={`wb-space-filter-btn ${spaceFilter === "project" ? "wb-space-filter-btn--active" : ""}`}
            onClick={() => setSpaceFilter("project")}
          >
            Projects ({projectCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={spaceFilter === "group"}
            className={`wb-space-filter-btn ${spaceFilter === "group" ? "wb-space-filter-btn--active" : ""}`}
            onClick={() => setSpaceFilter("group")}
          >
            Groups ({groupCount})
          </button>
        </div>

        {/* Search filter if workspaces > 3 */}
        {workspaces.length > 3 && (
          <div className="wb-space-search-box">
            <input
              type="search"
              className="wb-space-search-input"
              placeholder="Filter spaces by name..."
              value={spaceSearch}
              onChange={(e) => setSpaceSearch(e.target.value)}
              aria-label="Filter workspaces by name"
            />
            {spaceSearch && (
              <button
                type="button"
                className="wb-space-search-clear"
                onClick={() => setSpaceSearch("")}
                aria-label="Clear space search"
              >
                ✕
              </button>
            )}
          </div>
        )}

        {workspacesLoading ? (
          <Skeleton label="Loading team spaces" />
        ) : filteredWorkspaces.length === 0 ? (
          <div className="wb-empty wb-empty--compact">
            <p className="wb-empty__text">
              {spaceSearch ? "No spaces match your filter." : "No spaces in this category."}
            </p>
            {spaceSearch && (
              <button
                type="button"
                className="ui-button ui-button--quiet ui-button--sm"
                onClick={() => setSpaceSearch("")}
              >
                Clear search
              </button>
            )}
          </div>
        ) : (
          <ul className="wb-space-list">
            {filteredWorkspaces.map((ws) => (
              <li key={ws.id} className="wb-space-item">
                <div className="wb-space-item__main">
                  <Link to={`/w/${ws.id}/noticeboard`} className="wb-space-item__name">
                    {ws.kind === "project" && (
                      <span className="wb-space-kind-icon" aria-hidden="true">
                        🚀{" "}
                      </span>
                    )}
                    {ws.kind === "group" && (
                      <span className="wb-space-kind-icon" aria-hidden="true">
                        👥{" "}
                      </span>
                    )}
                    {ws.kind === "org" && (
                      <span className="wb-space-kind-icon" aria-hidden="true">
                        🏢{" "}
                      </span>
                    )}
                    {ws.name}
                  </Link>
                </div>
                <div className="wb-space-item__quick-nav">
                  <Link to={`/w/${ws.id}/noticeboard`} title="Noticeboard">
                    Noticeboard
                  </Link>
                  <span>·</span>
                  <Link to={`/w/${ws.id}/whiteboard`} title="Whiteboard">
                    Board
                  </Link>
                  <span>·</span>
                  <Link to={`/w/${ws.id}/chat`} title="Chat">
                    Chat
                  </Link>
                  <span>·</span>
                  <Link to={`/w/${ws.id}/todos`} title="Tasks">
                    Tasks
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
