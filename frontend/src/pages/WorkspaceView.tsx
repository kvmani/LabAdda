import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorStatus } from "../api";
import { kindLabel } from "../format";
import { useSession } from "../session";
import { useWorkspaces } from "../workspaces";
import type { Workspace } from "../types";
import { Noticeboard } from "./Noticeboard";
import { Todos } from "./Todos";
import { Chat } from "./Chat";
import { Board } from "./Board";
import { Members } from "./Members";
import { WorkspaceUsage } from "./WorkspaceUsage";
import { Breadcrumbs, PageHeader, Skeleton, Tabs } from "../ui";
import "./workspace.css";

type Detail = Workspace & { ancestors: { id: string; name: string }[] };
const TABS = [
  ["noticeboard", "Noticeboard"],
  ["board", "Whiteboard"],
  ["chat", "Chat"],
  ["todos", "Tasks"],
  ["members", "Members"],
  ["usage", "Storage"],
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
  const { session } = useSession();
  const navigate = useNavigate();
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
        const status = errorStatus(e);
        if (live && (status === 404 || status === 422)) setMissing(true);
      });
    return () => {
      live = false;
    };
  }, [
    workspaceId,
    listed?.role,
    listed?.archived,
    listed?.posting_policy,
    listed?.name,
    listed?.description,
  ]);

  if (missing)
    return (
      <div role="alert">
        <PageHeader
          title="Workspace not available"
          scope="This workspace does not exist or you do not have access to it."
          action={<Link to="/">Go to your home workspace</Link>}
        />
      </div>
    );
  if (!detail) return <Skeleton lines={5} label="Loading workspace…" />;
  const ws: Workspace = { ...detail, unread_chat: listed?.unread_chat ?? 0 };
  const tabs = TABS.map(([id, label]) => ({
    id,
    label: id === "chat" && ws.unread_chat > 0 ? `${label} (${ws.unread_chat} new)` : label,
  }));
  const crumbs = [...detail.ancestors].reverse().map((a) => ({ label: a.name, to: `/w/${a.id}/${tab}` }));

  return (
    <div className="workspace">
      {crumbs.length > 0 && <Breadcrumbs items={[...crumbs, { label: ws.name }]} />}
      <PageHeader
        title={ws.name}
        scope={`${kindLabel(ws.kind)} · ${accessLabel(ws)}${ws.description ? ` — ${ws.description}` : ""}`}
      />
      <Tabs
        label="Workspace features"
        tabs={tabs}
        selected={tab}
        onSelect={(id) => navigate(`/w/${ws.id}/${id}`)}
      >
        {tab === "noticeboard" && <Noticeboard ws={ws} key={ws.id} />}
        {tab === "todos" && <Todos ws={ws} key={ws.id} />}
        {tab === "chat" && <Chat ws={ws} key={ws.id} />}
        {tab === "board" && (
          <Board
            ws={ws}
            key={ws.id}
            userId={session?.user.id}
            maxUploadBytes={session?.limits.max_attachment_bytes}
          />
        )}
        {tab === "members" && <Members ws={ws} key={ws.id} />}
        {tab === "usage" && <WorkspaceUsage workspaceId={ws.id} key={ws.id} />}
      </Tabs>
    </div>
  );
}
