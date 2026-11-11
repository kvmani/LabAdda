import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
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
function value(data: unknown, key: string): string {
  if (key === "status" && typeof data === "string")
    return (
      (
        { todo: "To do", in_progress: "In progress", blocked: "Blocked", done: "Done" } as Record<
          string,
          string
        >
      )[data] ?? data
    );
  if (data === null) return "None";
  if (typeof data === "boolean") return data ? "Yes" : "No";
  if (Array.isArray(data))
    // History records a checklist as its list of entries.
    return (
      (data as ChecklistEntry[]).map((item) => `${item.done ? "✓" : "○"} ${item.title}`).join("; ") || "Empty"
    );
  if (typeof data === "object" && "display_name" in data) return String(data.display_name);
  if (typeof data === "string" || typeof data === "number") return String(data);
  return JSON.stringify(data) ?? "";
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
  const [open, setOpen] = useState(false),
    [page, setPage] = useState<Page | null>(null),
    [error, setError] = useState("");
  const generation = useRef(0);
  useEffect(() => {
    ++generation.current;
    setOpen(false);
    setPage(null);
    setError("");
    return () => {
      invalidate(generation);
    };
  }, [listId, taskId, revision]);
  async function load(before?: number) {
    const token = ++generation.current;
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
  if (!open)
    return (
      <button type="button" onClick={() => load()}>
        View task history
      </button>
    );
  return (
    <section aria-label="Task change history">
      <button
        type="button"
        onClick={() => {
          ++generation.current;
          setOpen(false);
          setPage(null);
        }}
      >
        Close task history
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!page && !error && <p role="status">Loading task history…</p>}
      {page && (
        <>
          <ol>
            {page.items.map((event) => (
              <li key={event.revision}>
                <p>
                  Revision {event.revision} ·{" "}
                  {event.action === "created"
                    ? "Created"
                    : event.action === "updated"
                      ? "Updated"
                      : "Tracking began"}{" "}
                  · {event.actor?.display_name ?? "Earlier author not recorded"} ·{" "}
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
            ))}
          </ol>
          {page.next_cursor && (
            <button type="button" onClick={() => load(page.next_cursor!)}>
              Older task changes
            </button>
          )}
        </>
      )}
    </section>
  );
}
