import { useEffect, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { accessDenied, api, ApiError, errorMessage, errorStatus, outcomeUnknown } from "../api";
import { useTaskUpdates } from "../taskUpdates";
import { TaskEditor, type Page, type Task } from "../components/TaskEditor";
import { TodoTaskCard } from "../components/TodoTaskCard";
import type { Workspace } from "../types";
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, TextInput } from "../ui";
import "./todos.css";

type List = { id: string; title: string; revision: number; workspace_id: string | null };

export function Todos({ ws }: { ws?: Workspace }) {
  const [lists, setLists] = useState<List[]>([]),
    [listCursor, setListCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<List | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]),
    [taskCursor, setTaskCursor] = useState<string | null>(null);
  const [title, setTitle] = useState(""),
    [rename, setRename] = useState("");
  const [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [taskLoading, setTaskLoading] = useState(false);
  const [creating, setCreating] = useState(false),
    [editing, setEditing] = useState<Task | null>(null),
    [editorKey, setEditorKey] = useState(0);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [renameConflict, setRenameConflict] = useState(false);
  const listAttempt = useRef<{ client_id: string; title: string; workspace_id: string | null } | null>(null);
  const selectedRef = useRef<string | null>(null);
  const generation = useRef(0),
    taskGeneration = useRef(0),
    editorGeneration = useRef(0);
  const writable = ws ? ws.can_write && !ws.archived : true;
  function failed(e: unknown) {
    setError(errorMessage(e));
    if (accessDenied(e)) {
      ++generation.current;
      ++taskGeneration.current;
      ++editorGeneration.current;
      setLoading(false);
      setTaskLoading(false);
      setListCursor(null);
      setTaskCursor(null);
      setLists([]);
      selectedRef.current = null;
      setSelected(null);
      setTasks([]);
      setCreating(false);
      setEditing(null);
    }
  }
  const updates = useTaskUpdates(ws ? [ws.id] : [], () =>
    failed(new ApiError(404, "not_found", "This workspace is no longer available.")),
  );
  async function loadLists(after?: string) {
    const token = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const result = await api<Page<List>>("/todos/lists", { params: { workspace_id: ws?.id, after } });
      if (token === generation.current) {
        setLists(result.items);
        setListCursor(result.next_cursor);
        return true;
      }
      return false;
    } catch (e: unknown) {
      if (token === generation.current) failed(e);
      return false;
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }
  async function loadTasks(listId: string, after?: string) {
    const token = ++taskGeneration.current;
    setTaskLoading(true);
    setTaskCursor(null);
    setError("");
    try {
      const result = await api<Page<Task>>(`/todos/lists/${listId}/tasks`, { params: { after } });
      if (token === taskGeneration.current) {
        setTasks(result.items);
        setTaskCursor(result.next_cursor);
        return true;
      }
      return false;
    } catch (e: unknown) {
      if (token === taskGeneration.current) failed(e);
      return false;
    } finally {
      if (token === taskGeneration.current) setTaskLoading(false);
    }
  }
  useEffect(() => {
    void loadLists();
    return () => {
      invalidate(generation);
      invalidate(taskGeneration);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload lists only when the workspace changes
  }, [ws?.id]);
  async function refreshShared() {
    const seen = updates.snapshot(),
      listId = selectedRef.current;
    // Refresh the visible cards in place, not page one: inserts or pagination
    // must never unmount a colleague's unsent comment or assignment choice.
    const visible = tasks.map((task) => task.id);
    if (!(await loadLists())) return;
    if (listId && selectedRef.current === listId) {
      if (visible.length === 0) {
        if (!(await loadTasks(listId))) return;
      } else {
        const token = ++taskGeneration.current;
        setTaskLoading(true);
        try {
          const rows = await Promise.all(
            visible.map((id) => api<Task>(`/todos/lists/${listId}/tasks/${id}`)),
          );
          if (token !== taskGeneration.current || selectedRef.current !== listId) return;
          setTasks(rows);
        } catch (e: unknown) {
          if (token === taskGeneration.current) failed(e);
          return;
        } finally {
          if (token === taskGeneration.current) setTaskLoading(false);
        }
      }
    }
    updates.acknowledge(seen);
    setMessage(
      "Displayed tasks checked. Refresh tasks to see new tasks or return to the first page. Refresh open comments separately.",
    );
  }
  function choose(row: List) {
    selectedRef.current = row.id;
    ++editorGeneration.current;
    ++taskGeneration.current;
    setSelected(row);
    setRename(row.title);
    setRenameConflict(false);
    setTasks([]);
    setCreating(false);
    setEditing(null);
    void loadTasks(row.id);
  }
  async function createList(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const creationGeneration = generation.current;
    try {
      listAttempt.current ??= { client_id: crypto.randomUUID(), title, workspace_id: ws?.id ?? null };
      const result = await api<List>("/todos/lists", { body: listAttempt.current });
      listAttempt.current = null;
      setUnconfirmed(false);
      setTitle("");
      if (creationGeneration !== generation.current) return;
      if (await loadLists()) {
        choose(result);
        setMessage("List saved.");
      }
    } catch (e: unknown) {
      failed(e);
      setUnconfirmed(outcomeUnknown(e));
      if (!outcomeUnknown(e)) listAttempt.current = null;
    } finally {
      setBusy(false);
    }
  }
  async function renameList(event: FormEvent) {
    event.preventDefault();
    if (busy || !selected) return;
    setBusy(true);
    setError("");
    const renameGeneration = generation.current,
      renameEditor = editorGeneration.current;
    try {
      const result = await api<List>(`/todos/lists/${selected.id}`, {
        method: "PUT",
        body: { title: rename, revision: selected.revision },
      });
      if (renameGeneration !== generation.current || renameEditor !== editorGeneration.current) return;
      setSelected(result);
      setLists((rows) => rows.map((r) => (r.id === result.id ? result : r)));
      setRenameConflict(false);
      setMessage("List renamed.");
    } catch (e: unknown) {
      if (renameGeneration === generation.current && renameEditor === editorGeneration.current) {
        failed(e);
        setRenameConflict(errorStatus(e) === 409);
      }
    } finally {
      setBusy(false);
    }
  }
  async function latestList() {
    if (!selected) return;
    setBusy(true);
    setError("");
    const epoch = editorGeneration.current;
    try {
      const row = await api<List>(`/todos/lists/${selected.id}`);
      if (epoch !== editorGeneration.current) return;
      setSelected(row);
      setRename(row.title);
      setRenameConflict(false);
      setLists((rows) => rows.map((r) => (r.id === row.id ? row : r)));
    } catch (e: unknown) {
      failed(e);
    } finally {
      setBusy(false);
    }
  }
  const audience = ws
    ? `Shared with readers of ${ws.name}.`
    : "Private to you. Administrators and colleagues cannot open these lists.";
  return (
    <section className="todos">
      {ws ? (
        <h2 className="todos__heading">To-do lists</h2>
      ) : (
        <PageHeader title="My To-do Lists" scope={audience} />
      )}
      {ws && <p className="todos__muted">{audience}</p>}
      {ws && updates.pending && (
        <div className="todos__notice" role="status">
          <span>
            Shared tasks or discussion may have changed. Refresh to check the latest saved work. Your drafts
            are kept.
          </span>
          <Button disabled={loading || taskLoading || busy} onClick={refreshShared}>
            Check shared updates
          </Button>
        </div>
      )}
      {!writable && <p className="todos__muted">This workspace is read-only. You can read its tasks.</p>}
      {error && <ErrorState message={error} title="Something went wrong" />}
      {message && <p role="status">{message}</p>}
      <Card
        title="Lists"
        level={3}
        actions={
          <Button icon="refresh" onClick={() => loadLists()}>
            Refresh lists
          </Button>
        }
      >
        <div className="todos__stack">
          {writable && (
            <form className="todos__inline" onSubmit={createList}>
              <TextInput
                label="New list title"
                maxLength={200}
                disabled={busy || unconfirmed}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <Button variant="primary" type="submit" disabled={busy || !title.trim()}>
                {unconfirmed ? "Retry same list creation" : "Create list"}
              </Button>
            </form>
          )}
          {unconfirmed && (
            <p className="todos__muted">
              List creation is unconfirmed. Retry the same request to recover it.
            </p>
          )}
          {loading ? (
            <Skeleton lines={3} label="Loading lists…" />
          ) : lists.length === 0 ? (
            <EmptyState title="No to-do lists in this scope yet.">
              {writable ? "Create a list above to start adding tasks." : "Lists will appear here."}
            </EmptyState>
          ) : (
            <nav aria-label="To-do lists">
              <ul className="todos__lists">
                {lists.map((row) => (
                  <li key={row.id}>
                    <Button
                      variant={selected?.id === row.id ? "primary" : "secondary"}
                      aria-pressed={selected?.id === row.id}
                      disabled={busy}
                      onClick={() => choose(row)}
                    >
                      {row.title}
                    </Button>
                  </li>
                ))}
              </ul>
            </nav>
          )}
          {listCursor && (
            <div>
              <Button onClick={() => loadLists(listCursor)}>More lists</Button>
            </div>
          )}
        </div>
      </Card>
      {selected && (
        <section className="todos__selected" aria-label="Selected to-do list">
          <Card
            title={selected.title}
            level={3}
            actions={
              <>
                <Button icon="refresh" onClick={() => loadTasks(selected.id)}>
                  Refresh tasks
                </Button>
                {writable && (
                  <Button
                    variant="primary"
                    icon="plus"
                    onClick={() => {
                      setCreating(true);
                      setEditing(null);
                      setEditorKey(++editorGeneration.current);
                    }}
                  >
                    New task
                  </Button>
                )}
              </>
            }
          >
            <div className="todos__stack">
              {writable && (
                <form className="todos__inline" onSubmit={renameList}>
                  <TextInput
                    label="List name"
                    maxLength={200}
                    value={rename}
                    onChange={(e) => setRename(e.target.value)}
                  />
                  <Button type="submit" disabled={busy || !rename.trim()}>
                    Rename list
                  </Button>
                </form>
              )}
              {renameConflict && (
                <p className="todos__muted">
                  Your list-name draft is kept. Loading the latest list will replace this draft.
                </p>
              )}
              {renameConflict && writable && (
                <div>
                  <Button disabled={busy} onClick={latestList}>
                    Load latest list (replaces draft)
                  </Button>
                </div>
              )}
            </div>
          </Card>
          {taskLoading && <Skeleton lines={3} label="Loading tasks…" />}
          {!taskLoading && tasks.length === 0 && (
            <EmptyState title="No tasks on this page.">
              {writable ? "Choose New task to add the first one." : undefined}
            </EmptyState>
          )}
          <ul className="todo-task-list">
            {tasks.map((task) => (
              <TodoTaskCard
                key={task.id}
                task={task}
                listId={selected.id}
                writable={writable}
                workspaceId={ws?.id}
                reload={() => {
                  if (selectedRef.current === selected.id) void loadTasks(selected.id);
                }}
                edit={() => {
                  setEditing(task);
                  setCreating(false);
                  setEditorKey(++editorGeneration.current);
                }}
              />
            ))}
          </ul>
          {taskCursor && (
            <div>
              <Button onClick={() => loadTasks(selected.id, taskCursor)}>More tasks</Button>
            </div>
          )}
          {writable && (creating || editing) && (
            <TaskEditor
              key={editorKey}
              listId={selected.id}
              initial={editing}
              cancel={() => {
                ++editorGeneration.current;
                setCreating(false);
                setEditing(null);
              }}
              saved={() => {
                if (editorGeneration.current !== editorKey) return;
                ++editorGeneration.current;
                setCreating(false);
                setEditing(null);
                setMessage("Task saved.");
                void loadTasks(selected.id);
              }}
            />
          )}
        </section>
      )}
    </section>
  );
}
