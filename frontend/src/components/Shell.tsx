import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { INSTANCE } from "../config";
import { realtime, type ConnState } from "../realtime";
import { useSession } from "../session";
import { treeOrder, useWorkspaces } from "../workspaces";
import type { Workspace } from "../types";
import { Notifications } from "./Notifications";

function RailItem({ ws, depth, current }: { ws: Workspace; depth: number; current: boolean }) {
  return (
    <li>
      <NavLink
        to={`/w/${ws.id}/noticeboard`}
        className={"rail-link" + (current ? " active" : "")}
        style={{ paddingLeft: `${0.75 + depth * 0.9}rem` }}
        aria-current={current ? "page" : undefined}
      >
        <span className="rail-name">{ws.name}</span>
        {ws.archived && <span className="tag">Archived</span>}
        {ws.unread_chat > 0 && <span className="badge" aria-label={`${ws.unread_chat} unread chat messages`}>{ws.unread_chat} new</span>}
      </NavLink>
    </li>
  );
}

const connLabel: Record<ConnState, string> = {
  online: "Live",
  connecting: "Connecting…",
  reconnecting: "Reconnecting…",
  offline: "Offline",
};

export function Shell({ children }: { children: ReactNode }) {
  const { session, signOut } = useSession();
  const { workspaces, reload, error } = useWorkspaces();
  const location = useLocation();
  const navigate = useNavigate();
  const [conn, setConn] = useState<ConnState>(realtime.state);
  const [showNotifications, setShowNotifications] = useState(false);
  const [operations, setOperations] = useState(false);
  const [unread, setUnread] = useState(0);
  const currentId = location.pathname.match(/^\/w\/([^/]+)/)?.[1];

  useEffect(() => {
    let live = true;
    api<{"usage.read": boolean}>("/capabilities").then(c => {if (live) setOperations(c["usage.read"]);}).catch(()=>{if(live) setOperations(false);});
    return ()=>{live=false;};
  }, [location.pathname]);

  useEffect(() => realtime.onState(setConn) as () => void, []);
  useEffect(() => {
    const load = () => api("/notifications", { params: { limit: 1 } }).then((r) => setUnread(r.unread)).catch(() => undefined);
    load();
    const t = window.setInterval(load, 30000);
    return () => window.clearInterval(t);
  }, [location.pathname]);
  const currentRef = useRef(currentId);
  currentRef.current = currentId;
  useEffect(() => {
    // Membership changes arrive as access signals; refresh the rail.
    const unsubs = workspaces.map((w) => realtime.subscribe(w.id, (ev) => {
      if (ev.type === "revoked" || ev.type === "access_changed") reload();
      if (ev.type === "chat.message" && ev.message.author?.id !== session?.user.id && currentRef.current !== w.id) reload();
    }));
    return () => unsubs.forEach((u) => u());
  }, [workspaces.map((w) => w.id).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const tree = treeOrder(workspaces);
  const projects = workspaces.filter((w) => w.kind === "project");
  const groups = workspaces.filter((w) => w.kind === "group");

  return (
    <div className="shell">
      {/* Moves focus programmatically: a "#main" href would resolve against <base href> under a prefix. */}
      <a href="#main" className="skip-link" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>Skip to main content</a>
      <header className="topbar">
        <Link to="/" className="brand">LabAdda</Link>
        {INSTANCE !== "pilot" && <span className="tag instance">{INSTANCE}</span>}
        <label className="switcher">
          <span className="sr-only">Switch workspace</span>
          <select value={currentId ?? ""} onChange={(e) => e.target.value && navigate(["notes", "usage", "operations"].includes(e.target.value) ? `/${e.target.value}` : `/w/${e.target.value}/noticeboard`)}>
            <option value="">Choose workspace…</option>
            {tree.map(({ ws, depth }) => <option key={ws.id} value={ws.id}>{"· ".repeat(depth) + ws.name}</option>)}
            {projects.map((w) => <option key={w.id} value={w.id}>Project: {w.name}</option>)}
            {groups.map((w) => <option key={w.id} value={w.id}>Group: {w.name}</option>)}
            <option value="notes">My Notes</option>
            <option value="usage">My storage usage</option>
            {operations && <option value="operations">Operational observations</option>}
          </select>
        </label>
        <span className={`conn conn-${conn}`} role="status">● {connLabel[conn]}</span>
        <button className="ghost" onClick={() => setShowNotifications((v) => !v)} aria-expanded={showNotifications} aria-controls="notifications">
          Notifications{unread > 0 ? ` (${unread} unread)` : ""}
        </button>
        {session?.user.is_admin && <NavLink to="/admin" className="ghost-link">Administration</NavLink>}
        <span className="who">{session?.user.display_name}</span>
        <button className="ghost" onClick={() => signOut()}>Sign out</button>
      </header>
      {showNotifications && <Notifications onClose={() => setShowNotifications(false)} onChange={setUnread} />}
      <nav className="rail" aria-label="Workspaces">
        {operations && <NavLink to="/operations" className="rail-link">Operational observations</NavLink>}
        <NavLink to="/usage" className={({ isActive }) => "rail-link" + (isActive ? " active" : "")}>My storage usage</NavLink>
        <NavLink to="/todos" className="rail-link">My To-do Lists <span className="muted small">private</span></NavLink>
        <NavLink to="/notes" className={({ isActive }) => "rail-link notes-link" + (isActive ? " active" : "")}>My Notes <span className="muted small">private</span></NavLink>
        {error && <p className="error small">{error}</p>}
        {tree.length > 0 && <h2 className="rail-heading">Organization</h2>}
        <ul>{tree.map(({ ws, depth }) => <RailItem key={ws.id} ws={ws} depth={depth} current={ws.id === currentId} />)}</ul>
        {projects.length > 0 && <h2 className="rail-heading">Projects</h2>}
        <ul>{projects.map((w) => <RailItem key={w.id} ws={w} depth={0} current={w.id === currentId} />)}</ul>
        <h2 className="rail-heading">My groups</h2>
        <ul>{groups.map((w) => <RailItem key={w.id} ws={w} depth={0} current={w.id === currentId} />)}</ul>
        <Link to="/groups/new" className="rail-action">+ New group</Link>
      </nav>
      <main className="content" id="main" tabIndex={-1}>{children}</main>
    </div>
  );
}
