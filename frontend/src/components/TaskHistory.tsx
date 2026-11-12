import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import { Button } from "../ui";
import "./task.css";
import { api, errorMessage } from "../api";

type Change = {
  revision: number;
  actor_id: string | null;
  actor: { display_name: string } | null;
  action: string;
  changes: Record<string, { before: unknown; after: unknown }>;
  created_at: string;
};
type Page = { items: Change[]; next_cursor: number | null };
const labels: Record<string, string> = {
  assignee: "Assignee",
  title: "Title",
  description: "Description",
  due_date: "Due date",
  priority: "Priority",
  checklist: "Checklist",
  done: "Completion",
  status: "Workflow state",
};
type ChecklistEntry = { title: string; done: boolean };

const workflowNames: Record<string, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
};

const actionNames: Record<string, string> = {
  created: "Created",
  updated: "Updated",
};

function describeChecklist(entries: ChecklistEntry[]): string {
  // History records a checklist as its list of entries.
  const lines = entries.map((item) => `${item.done ? "✓" : "○"} ${item.title}`);
  return lines.join("; ") || "Empty";
}

function value(data: unknown, key: string): string {
  if (key === "status" && typeof data === "string") return workflowNames[data] ?? data;
  if (data === null) return "None";
  if (typeof data === "boolean") return data ? "Yes" : "No";
  if (Array.isArray(data)) return describeChecklist(data as ChecklistEntry[]);
  if (typeof data === "object" && "display_name" in data) return String(data.display_name);
  if (typeof data === "string" || typeof data === "number") return String(data);
  return JSON.stringify(data) ?? "";
}

function HistoryEntry({ event }: { event: Change }) {
  const actionName = actionNames[event.action] ?? "Tracking began";
  return (
    <li>
      <p>
        Revision {event.revision} · {actionName} ·{" "}
        {event.actor?.display_name ?? "Earlier author not recorded"} ·{" "}
        {new Date(event.created_at).toLocaleString()}
      </p>
      {event.action === "baseline" && (
        <p>History tracking began here. Earlier edits and their authors were not recorded.</p>
      )}
      <ul>
        {Object.entries(event.changes).map(([key, change]) => (
          <li key={key}>
            {labels[key] ?? key}: {value(change.before, key)} → {value(change.after, key)}
          </li>
        ))}
      </ul>
    </li>
  );
}

export function TaskHistory({
  listId,
  taskId,
  revision,
}: {
  listId: string;
  taskId: string;
  revision: number;
}) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState("");
  const generation = useRef(0);

  useEffect(() => {
    generation.current += 1;
    setOpen(false);
    setPage(null);
    setError("");
    return () => {
      invalidate(generation);
    };
  }, [listId, taskId, revision]);

  async function load(before?: number) {
    generation.current += 1;
    const token = generation.current;
    setOpen(true);
    setPage(null);
    setError("");
    try {
      const result = await api<Page>(`/todos/lists/${listId}/tasks/${taskId}/history`, {
        params: { before },
      });
      if (token === generation.current) setPage(result);
    } catch (e: unknown) {
      if (token === generation.current) setError(errorMessage(e));
    }
  }

  function close() {
    generation.current += 1;
    setOpen(false);
    setPage(null);
  }

  if (!open) {
    return (
      <Button size="sm" onClick={() => load()}>
        View task history
      </Button>
    );
  }
  return (
    <section className="task-panel" aria-label="Task change history">
      <Button size="sm" onClick={close}>
        Close task history
      </Button>
      {error && (
        <p className="task__error" role="alert">
          {error}
        </p>
      )}
      {!page && !error && <p role="status">Loading task history…</p>}
      {page && (
        <>
          <ol>
            {page.items.map((event) => (
              <HistoryEntry key={event.revision} event={event} />
            ))}
          </ol>
          {page.next_cursor && (
            <Button size="sm" onClick={() => load(page.next_cursor!)}>
              Older task changes
            </Button>
          )}
        </>
      )}
    </section>
  );
}
