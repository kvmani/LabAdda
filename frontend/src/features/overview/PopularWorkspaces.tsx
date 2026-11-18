import type { PopularWorkspace } from "./types";

type Props = {
  workspaces: PopularWorkspace[];
};

export function PopularWorkspaces({ workspaces }: Props) {
  if (!workspaces.length) {
    return <p className="cockpit-muted">Unit activity is not measured or is protected for small groups.</p>;
  }

  return (
    <div className="popular-workspaces-list" role="region" aria-label="Most active workspaces">
      {workspaces.map((ws, index) => (
        <div key={ws.id} className="popular-ws-card">
          <div className="popular-ws-card__rank">#{index + 1}</div>
          <div className="popular-ws-card__main">
            <div className="popular-ws-card__title-row">
              <span className="popular-ws-card__name">
                {ws.kind === "project" && <span aria-hidden="true">🚀 </span>}
                {ws.kind === "group" && <span aria-hidden="true">👥 </span>}
                {ws.kind === "org" && <span aria-hidden="true">🏢 </span>}
                {ws.name}
              </span>
              <span className={`cockpit-badge cockpit-badge--${ws.kind}`}>
                {ws.kind === "org" ? "Unit" : ws.kind === "project" ? "Project" : "Group"}
              </span>
            </div>

            <div className="popular-ws-card__stats">
              <span>👥 {ws.active_people} active people (rounded)</span>
              <span className="cockpit-separator">·</span>
              <span className="popular-ws-card__steward-status">
                {ws.has_steward ? "✓ Steward active" : "⚠️ Needs steward"}
              </span>
            </div>
          </div>

          <div className="popular-ws-card__total">
            <span className="popular-ws-card__total-count">{ws.total_items}</span>
            <span className="popular-ws-card__total-label">Items</span>
          </div>
        </div>
      ))}
    </div>
  );
}
