import { useEffect, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { api } from "../api";
import { kindLabel } from "../format";
import { useWorkspaces } from "../workspaces";
import type { Workspace } from "../types";
import { Noticeboard } from "./Noticeboard";
import { Chat } from "./Chat";
import { Board } from "./Board";
import { Members } from "./Members";

type Detail = Workspace & { ancestors: { id: string; name: string }[] };
const TABS = [
  ["noticeboard", "Noticeboard"],
  ["board", "Whiteboard"],
  ["chat", "Chat"],
  ["members", "Members"],
] as const;

export function accessLabel(ws: Workspace): string {
  const parts = [ws.role === "steward" ? "Steward" : ws.role === "member" ? "Member" : "Inherited member"];
  if (ws.archived) parts.push("Archived · read-only");
  else if (!ws.can_write) parts.push("Read-only");
  return parts.join(" · ");
}

export function WorkspaceView() {
  const { workspaceId = "", tab = "noticeboard" } = useParams();
  const { workspaces } = useWorkspaces();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [missing, setMissing] = useState(false);
  const listed = workspaces.find((w) => w.id === workspaceId);

  useEffect(() => {
    // Reset only when switching workspace; background refreshes keep the view (and any typed input) mounted.
    setDetail((d) => (d?.id === workspaceId ? d : null));
    setMissing(false);
    let live = true;
    api<Detail>(`/workspaces/${workspaceId}`)
      .then((d) => live && setDetail(d))
      .catch((e) => {
        if (live && (e.status === 404 || e.status === 422)) setMissing(true);
      });
    return () => {
      live = false;
    };
  }, [workspaceId, listed?.role, listed?.archived, listed?.posting_policy, listed?.name, listed?.description]);

  if (missing)
    return (
      <section className="state" role="alert">
        <h1>Workspace not available</h1>
        <p>This workspace does not exist or you do not have access to it.</p>
        <Link to="/">Go to your home workspace</Link>
      </section>
    );
  if (!detail) return <p className="state">Loading workspace…</p>;
  const ws: Workspace = { ...detail, unread_chat: listed?.unread_chat ?? 0 };

  return (
    <div className="workspace">
      <header className="ws-header">
        {detail.ancestors.length > 0 && (
          <nav aria-label="Parent units" className="crumbs">
            {[...detail.ancestors].reverse().map((a) => (
              <Link key={a.id} to={`/w/${a.id}/${tab}`}>{a.name}</Link>
            ))}
          </nav>
        )}
        <h1>
          {ws.name} <span className="tag">{kindLabel(ws.kind)}</span>
        </h1>
        <p className="muted">{accessLabel(ws)}{ws.description ? ` — ${ws.description}` : ""}</p>
        <nav className="tabs" aria-label="Workspace features">
          {TABS.map(([key, label]) => (
            <NavLink key={key} to={`/w/${ws.id}/${key}`} className={() => "tab" + (tab === key ? " active" : "")} aria-current={tab === key ? "page" : undefined}>
              {label}
              {key === "chat" && ws.unread_chat > 0 ? ` (${ws.unread_chat} new)` : ""}
            </NavLink>
          ))}
        </nav>
      </header>
      {tab === "noticeboard" && <Noticeboard ws={ws} key={ws.id} />}
      {tab === "chat" && <Chat ws={ws} key={ws.id} />}
      {tab === "board" && <Board ws={ws} key={ws.id} />}
      {tab === "members" && <Members ws={ws} key={ws.id} />}
    </div>
  );
}
