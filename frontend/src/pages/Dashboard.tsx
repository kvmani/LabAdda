import { useRef } from "react";
import type { OpenedNotification } from "../types";
import { Link, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { fmtTime } from "../format";
import { Button, Card, ErrorState, PageHeader, Skeleton } from "../ui";
import { useDashboardOverview as useOverview, type Overview } from "../features/home/useDashboardOverview";
import "./dashboard.css";

function dueLabel(dueDate: string, today: string): string {
  if (dueDate < today) return "Overdue";
  return dueDate === today ? "Due today" : "Due";
}

function TasksCard({ data }: { data: Overview }) {
  return (
    <Card title="Active work and deadlines">
      <div className="daily-dashboard__panel">
        <p>Up to 25 personal or assigned tasks, earliest due first.</p>
        {!data.tasks.length ? (
          <p>No active tasks in this loaded view.</p>
        ) : (
          <ul>
            {data.tasks.map((task) => (
              <li key={task.id}>
                <Link to={task.workspace_id ? `/w/${task.workspace_id}/todos` : "/todos"}>{task.title}</Link>
                <p>
                  {task.status.replace(/_/g, " ")} · {task.priority} priority
                  {task.due_date ? ` · ${dueLabel(task.due_date, data.today)} ${task.due_date}` : ""}
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
  );
}

function UpdatesCard({ data, open }: { data: Overview; open: (id: string) => void }) {
  return (
    <Card title="Mentions and updates">
      <div className="daily-dashboard__panel">
        <p>Up to 10 recent visible notifications.</p>
        {!data.updates.length ? (
          <p>No recent updates in this loaded window.</p>
        ) : (
          <ul>
            {data.updates.map((item) => (
              <li key={item.id}>
                <Button variant="quiet" onClick={() => open(item.id)}>
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
  );
}

function NotesCard({ data }: { data: Overview }) {
  return (
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
  );
}

function ChatsCard({ data }: { data: Overview }) {
  return (
    <Card title="Unread conversations">
      <div className="daily-dashboard__panel">
        {!data.chats.length ? (
          <p>No unread chats in this loaded view.</p>
        ) : (
          <ul>
            {data.chats.map((chat) => (
              <li key={chat.workspace_id}>
                <Link to={`/w/${chat.workspace_id}/chat`}>{chat.workspace_name}</Link> · {chat.unread} unread
              </li>
            ))}
          </ul>
        )}
        {data.chats_more && <p>More unread spaces appear in workspace navigation.</p>}
      </div>
    </Card>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const { data, error, setError, loading, changed, load, generation } = useOverview();
  const openGeneration = useRef(0);

  async function openUpdate(id: string) {
    const token = generation.current;
    openGeneration.current += 1;
    const choice = openGeneration.current;
    const isCurrent = () => token === generation.current && choice === openGeneration.current;
    setError("");
    try {
      const result = await api<OpenedNotification>(`/notifications/${id}/open`, { method: "POST" });
      if (!isCurrent()) return;
      const link = result.link;
      void navigate(
        link.view === "calendar"
          ? "/calendar"
          : link.view === "notes"
            ? "/notes"
            : `/w/${link.workspace_id}/${link.view}`,
      );
    } catch (e: unknown) {
      if (isCurrent()) setError(errorMessage(e));
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
            <TasksCard data={data} />
            <UpdatesCard data={data} open={openUpdate} />
            <NotesCard data={data} />
            <ChatsCard data={data} />
          </div>
        </>
      )}
    </section>
  );
}
