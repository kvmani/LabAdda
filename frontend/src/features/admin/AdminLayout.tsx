import { useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, Select, Skeleton, Tag } from "../../ui";
import { SECTIONS } from "./console";
import { useConsole } from "./useConsole";
import "./admin.css";

/** Console navigation reflects current server authority, not administrator-looking links. */
export function AdminLayout() {
  const location = useLocation();
  return <ConsoleFrame key={location.pathname} />;
}

function ConsoleFrame() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [retry, setRetry] = useState(0);
  const result = useConsole(pathname, retry);
  if (!result) return <Skeleton label="Checking administration access" />;
  if (result.forbidden) return <Navigate to="/" replace />;
  if (!result.access) return <ErrorState message={result.error} onRetry={() => setRetry(retry + 1)} />;
  const access = result.access;
  const entries = SECTIONS.filter((entry) => access.sections.includes(entry.key));
  // A unit administrator has no overview; opening Administration lands on their first page.
  const first = entries[0];
  if (pathname === "/admin" && !access.sections.includes("overview") && first)
    return <Navigate to={first.path} replace />;
  const selected = SECTIONS.find(
    (entry) =>
      entry.path === pathname || pathname === entry.path + "/basic" || pathname === entry.path + "/setup",
  );
  const allowed = selected && access.sections.includes(selected.key);
  return (
    <div className="admin-console">
      <aside className="admin-console__navigation">
        <p className="admin-console__title">Administration</p>
        {access.read_only && <Tag>Read-only access</Tag>}
        {access.unit_admin && !access.read_only && <Tag>Unit administrator</Tag>}
        <nav aria-label="Administration" className="admin-console__links">
          {entries.map((entry) => (
            <NavLink key={entry.key} to={entry.path} end={entry.key === "overview"}>
              {entry.label}
            </NavLink>
          ))}
        </nav>
        <div className="admin-console__switcher">
          <Select
            label="Administration section"
            value={allowed ? selected.path : ""}
            placeholder={allowed ? undefined : "Choose a section"}
            options={entries.map((entry) => ({ value: entry.path, label: entry.label }))}
            onChange={(event) => navigate(event.target.value)}
          />
        </div>
      </aside>
      <div className="admin-console__content">
        {allowed ? (
          <Outlet context={access} />
        ) : selected ? (
          <ErrorState
            title="This section needs administrator access"
            message="Choose an available read-only section from the administration navigation."
          />
        ) : (
          <EmptyState title="Administration page not found">Choose a section from the navigation.</EmptyState>
        )}
      </div>
    </div>
  );
}
