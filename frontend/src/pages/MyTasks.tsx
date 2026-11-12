import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useTaskUpdates } from "../taskUpdates";
import { useWorkspaces } from "../workspaces";
import { Button, Card, EmptyState, ErrorState, PageHeader, Select, Skeleton } from "../ui";
import "../components/task.css";
import "./todos.css";

type Task = {
  id: string;
  list_id: string;
  list_title: string;
  workspace_id: string | null;
  title: string;
  description: string;
  status: string;
  due_date: string | null;
  priority: string;
};
type Page = { items: Task[]; next_cursor: string | null; restart_required: boolean };
const states: Record<string, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
};
/** Newest-first page of tasks assigned to or owned by the signed-in person. */
function useMyTasks(workspaceIds: string[]) {
  const [state, setState] = useState("");
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const visibility = [...workspaceIds].sort().join("|");

  const updates = useTaskUpdates(workspaceIds, () => {
    generation.current += 1;
    setPage(null);
    setLoading(false);
  });

  async function load(after?: string) {
    const seenVersion = updates.snapshot();
    generation.current += 1;
    const token = generation.current;
    const isCurrent = () => token === generation.current;
    setPage(null);
    setError("");
    setLoading(true);
    try {
      const result = await api<Page>("/todos/mine", { params: { status: state, after } });
      if (isCurrent()) {
        setPage(result);
        if (after === undefined) updates.acknowledge(seenVersion);
      }
    } catch (e: unknown) {
      if (isCurrent()) setError(errorMessage(e));
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    return () => {
      invalidate(generation);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the filter or the visible workspaces change
  }, [state, visibility]);

  function changeState(nextState: string) {
    generation.current += 1;
    setPage(null);
    setState(nextState);
  }

  return { state, page, error, loading, updates, load, changeState };
}

function TaskCard({ task, workspaceName }: { task: Task; workspaceName: string | undefined }) {
  const where = task.workspace_id ? (workspaceName ?? "Shared workspace") : "Private list";
  const listLink = task.workspace_id ? `/w/${task.workspace_id}/todos` : "/todos";
  const excerpt = task.description.slice(0, 200) + (task.description.length > 200 ? "…" : "");
  return (
    <Card title={task.title}>
      <div className="task-card">
        <p className="task-card__meta">
          {states[task.status]} · {task.priority} priority
          {task.due_date ? ` · Due ${task.due_date}` : ""}
        </p>
        <p>{excerpt}</p>
        <p className="task-card__meta">
          {where} · {task.list_title}
        </p>
        <Link to={listLink}>Open list: {task.list_title}</Link>
      </div>
    </Card>
  );
}

function TaskPage({ page, load }: { page: Page; load: (after?: string) => Promise<void> }) {
  const { workspaces } = useWorkspaces();
  const nameOf = (id: string | null) => workspaces.find((workspace) => workspace.id === id)?.name;
  return (
    <>
      {page.restart_required && (
        <p role="status">Access changed while loading. Refresh My Tasks to start again.</p>
      )}
      {page.items.length === 0 && (
        <EmptyState title="No personal or assigned tasks match this filter.">
          Tasks you create in My To-do Lists, or that colleagues assign to you, appear here.
        </EmptyState>
      )}
      <ul className="todo-task-list">
        {page.items.map((task) => (
          <li key={task.id}>
            <TaskCard task={task} workspaceName={nameOf(task.workspace_id)} />
          </li>
        ))}
      </ul>
      {page.next_cursor && <Button onClick={() => load(page.next_cursor!)}>More My Tasks</Button>}
    </>
  );
}

export function MyTasks() {
  const { workspaces } = useWorkspaces();
  const { state, page, error, loading, updates, load, changeState } = useMyTasks(
    workspaces.map((workspace) => workspace.id),
  );
  return (
    <section className="todos">
      <PageHeader
        title="My Tasks"
        scope="Your personal tasks and shared tasks assigned to you in spaces you can currently access."
      />
      {updates.pending && (
        <p role="status">Shared assignments may have changed. Refresh My Tasks to check current work.</p>
      )}
      <div className="todos__inline">
        <Select
          label="My Tasks state"
          value={state}
          onChange={(event) => changeState(event.target.value)}
          options={[
            { value: "", label: "All states" },
            ...Object.entries(states).map(([value, label]) => ({ value, label })),
          ]}
        />
        <Button icon="refresh" onClick={() => load()} disabled={loading}>
          Refresh My Tasks
        </Button>
      </div>
      {loading && <Skeleton lines={3} label="Loading My Tasks…" />}
      {error && (
        <ErrorState message={error} title="My Tasks could not be loaded" onRetry={() => void load()} />
      )}
      {page && <TaskPage page={page} load={load} />}
    </section>
  );
}
