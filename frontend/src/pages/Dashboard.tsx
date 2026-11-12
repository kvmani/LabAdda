import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import type { OpenedNotification } from "../types";
import { Link, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { realtime } from "../realtime";
import { useWorkspaces } from "../workspaces";
import { fmtTime } from "../format";
import { Button, Card, ErrorState, PageHeader, Skeleton } from "../ui";
import "./dashboard.css";

type Work = {
  id: string;
  list_id: string;
  list_title: string;
  workspace_id: string | null;
  workspace_name: string | null;
  title: string;
  due_date: string | null;
  priority: string;
  status: string;
};
type Update = {
  id: string;
  kind: string;
  title: string;
  read: boolean;
  workspace: { id: string; name: string } | null;
};
type Overview = {
  today: string;
  timezone: string;
  tasks: Work[];
  tasks_more: boolean;
  notes: { id: string; title: string; due_at: string }[];
  notes_more: boolean;
  updates: Update[];
  chats: { workspace_id: string; workspace_name: string; unread: number }[];
  chats_more: boolean;
  restart_required: boolean;
  observed_at: string;
};
export function Dashboard() {
  const { workspaces } = useWorkspaces(),
    navigate = useNavigate();
  const visibility = workspaces
    .map((row) => row.id)
    .sort()
    .join("|");
  const [data, setData] = useState<Overview | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [changed, setChanged] = useState(false);
  const generation = useRef(0),
    signals = useRef(0),
    openGeneration = useRef(0);
  async function load() {
    const token = ++generation.current,
      seen = signals.current;
    setLoading(true);
    setError("");
    setData(null);
    try {
      const result = await api<Overview>("/dashboard");
      if (token === generation.current) {
        setData(result);
        if (seen === signals.current) setChanged(false);
      }
    } catch (e: unknown) {
      if (token === generation.current)
        setError(errorMessage(e) + " The overview is unavailable; refresh to try again.");
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }
  useEffect(() => {
    void load();
    let active = true;
    const stops = (visibility ? visibility.split("|") : []).map((id) =>
      realtime.subscribe(id, (event) => {
        if (!active) return;
        if (
          ["tasks.changed", "chat.message", "noticeboard.changed", "subscribed", "access_changed"].includes(
            event.type,
          )
        ) {
          ++signals.current;
          setChanged(true);
        }
        if (["revoked", "subscribe_failed", "session_ended"].includes(event.type)) {
          ++generation.current;
          ++signals.current;
          setData(null);
          setLoading(false);
          setChanged(true);
        }
      }),
    );
    return () => {
      active = false;
      invalidate(generation);
      stops.forEach((stop) => stop());
    };
  }, [visibility]);
  async function openUpdate(id: string) {
    const token = generation.current,
      choice = ++openGeneration.current;
    setError("");
    try {
      const result = await api<OpenedNotification>(`/notifications/${id}/open`, { method: "POST" });
      if (token !== generation.current || choice !== openGeneration.current) return;
      const link = result.link;
      navigate(link.view === "notes" ? "/notes" : `/w/${link.workspace_id}/${link.view}`);
    } catch (e: unknown) {
      if (token === generation.current && choice === openGeneration.current) setError(errorMessage(e));
    }
  }
  return (
    <section className="daily-dashboard">
      <PageHeader
        title="My day"
        scope="Your personal work and currently accessible shared assignments, reminders and conversations."
        action={
          <Button icon="refresh" disabled={loading} onClick={load}>
            Refresh My day
          </Button>
        }
      />
      <p>
        <Link to="/preferences">Manage alert preferences</Link>
      </p>
      {changed && (
        <p className="daily-dashboard__notice" role="status">
          Activity may have changed. Refresh My day to review current work.
        </p>
      )}
      {loading && !data && <Skeleton lines={4} label="Loading My day…" />}
      {loading && data && <p role="status">Loading My day…</p>}
      {error && <ErrorState message={error} title="My day could not be loaded" onRetry={() => void load()} />}
      {data && (
        <>
          <p className="daily-dashboard__muted">
            Calendar date {data.today} · {data.timezone} · Checked {fmtTime(data.observed_at, data.timezone)}
          </p>
          {data.restart_required && (
            <p role="status">Access changed during loading. Refresh to rebuild this overview.</p>
          )}
          <div className="daily-dashboard__grid">
            <Card title="Active work and deadlines">
              <div className="daily-dashboard__panel">
                <p>Up to 25 personal or assigned tasks, earliest due first.</p>
                {!data.tasks.length ? (
                  <p>No active tasks in this loaded view.</p>
                ) : (
                  <ul>
                    {data.tasks.map((task) => (
                      <li key={task.id}>
                        <Link to={task.workspace_id ? `/w/${task.workspace_id}/todos` : "/todos"}>
                          {task.title}
                        </Link>
                        <p>
                          {task.status.replace(/_/g, " ")} · {task.priority} priority
                          {task.due_date
                            ? ` · ${task.due_date < data.today ? "Overdue" : task.due_date === data.today ? "Due today" : "Due"} ${task.due_date}`
                            : ""}
                        </p>
                        <p className="daily-dashboard__muted">
                          {task.workspace_name ?? "Private list"} · {task.list_title}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
                {data.tasks_more && <p>More active work is available.</p>}
                <Link to="/my-tasks">Open My Tasks</Link>
              </div>
            </Card>
            <Card title="Mentions and updates">
              <div className="daily-dashboard__panel">
                <p>Up to 10 recent visible notifications.</p>
                {!data.updates.length ? (
                  <p>No recent updates in this loaded window.</p>
                ) : (
                  <ul>
                    {data.updates.map((item) => (
                      <li key={item.id}>
                        <Button variant="quiet" onClick={() => openUpdate(item.id)}>
                          {item.read ? "" : "Unread · "}
                          {item.kind}: {item.title}
                        </Button>
                        {item.workspace && <p className="daily-dashboard__muted">{item.workspace.name}</p>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>
            <Card title="Private note deadlines">
              <div className="daily-dashboard__panel">
                <p>Up to 10 earliest dated notes, visible only to you.</p>
                {!data.notes.length ? (
                  <p>No dated notes in this loaded view.</p>
                ) : (
                  <ul>
                    {data.notes.map((note) => (
                      <li key={note.id}>
                        <Link to="/notes">{note.title || "Private note"}</Link> ·{" "}
                        {fmtTime(note.due_at, data.timezone)}
                      </li>
                    ))}
                  </ul>
                )}
                {data.notes_more && <p>More dated notes are available.</p>}
                <Link to="/notes">Open My Notes</Link>
              </div>
            </Card>
            <Card title="Unread conversations">
              <div className="daily-dashboard__panel">
                {!data.chats.length ? (
                  <p>No unread chats in this loaded view.</p>
                ) : (
                  <ul>
                    {data.chats.map((chat) => (
                      <li key={chat.workspace_id}>
                        <Link to={`/w/${chat.workspace_id}/chat`}>{chat.workspace_name}</Link> · {chat.unread}{" "}
                        unread
                      </li>
                    ))}
                  </ul>
                )}
                {data.chats_more && <p>More unread spaces appear in workspace navigation.</p>}
              </div>
            </Card>
          </div>
        </>
      )}
    </section>
  );
}
