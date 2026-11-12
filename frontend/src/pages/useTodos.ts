import { useEffect, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { accessDenied, api, ApiError, errorMessage, errorStatus, outcomeUnknown } from "../api";
import { useTaskUpdates } from "../taskUpdates";
import type { Page, Task } from "../components/TaskEditor";
import type { Workspace } from "../types";

export type List = { id: string; title: string; revision: number; workspace_id: string | null };

type ListAttempt = { client_id: string; title: string; workspace_id: string | null };

/**
 * All state and requests of the to-do screen. Three counters guard stale replies: `generation` for
 * lists, `taskGeneration` for the task page, `editorGeneration` for the open editor and rename form.
 */
export function useTodos(ws: Workspace | undefined) {
  const [lists, setLists] = useState<List[]>([]);
  const [listCursor, setListCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<List | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskCursor, setTaskCursor] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [rename, setRename] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [taskLoading, setTaskLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [editorKey, setEditorKey] = useState(0);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [renameConflict, setRenameConflict] = useState(false);
  const listAttempt = useRef<ListAttempt | null>(null);
  const selectedRef = useRef<string | null>(null);
  const generation = useRef(0);
  const taskGeneration = useRef(0);
  const editorGeneration = useRef(0);

  function failed(e: unknown) {
    setError(errorMessage(e));
    if (!accessDenied(e)) return;
    generation.current += 1;
    taskGeneration.current += 1;
    editorGeneration.current += 1;
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

  const updates = useTaskUpdates(ws ? [ws.id] : [], () =>
    failed(new ApiError(404, "not_found", "This workspace is no longer available.")),
  );

  async function loadLists(after?: string) {
    generation.current += 1;
    const token = generation.current;
    setLoading(true);
    setError("");
    try {
      const result = await api<Page<List>>("/todos/lists", { params: { workspace_id: ws?.id, after } });
      if (token !== generation.current) return false;
      setLists(result.items);
      setListCursor(result.next_cursor);
      return true;
    } catch (e: unknown) {
      if (token === generation.current) failed(e);
      return false;
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }

  async function loadTasks(listId: string, after?: string) {
    taskGeneration.current += 1;
    const token = taskGeneration.current;
    setTaskLoading(true);
    setTaskCursor(null);
    setError("");
    try {
      const result = await api<Page<Task>>(`/todos/lists/${listId}/tasks`, { params: { after } });
      if (token !== taskGeneration.current) return false;
      setTasks(result.items);
      setTaskCursor(result.next_cursor);
      return true;
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

  /** Re-reads the cards already on screen in place, so a colleague's unsent comment is never unmounted. */
  async function refreshVisibleTasks(listId: string, visibleIds: string[]) {
    taskGeneration.current += 1;
    const token = taskGeneration.current;
    setTaskLoading(true);
    try {
      const rows = await Promise.all(visibleIds.map((id) => api<Task>(`/todos/lists/${listId}/tasks/${id}`)));
      if (token !== taskGeneration.current || selectedRef.current !== listId) return false;
      setTasks(rows);
      return true;
    } catch (e: unknown) {
      if (token === taskGeneration.current) failed(e);
      return false;
    } finally {
      if (token === taskGeneration.current) setTaskLoading(false);
    }
  }

  async function refreshShared() {
    const seenVersion = updates.snapshot();
    const listId = selectedRef.current;
    // Refresh the visible cards in place, not page one: inserts or pagination
    // must never unmount a colleague's unsent comment or assignment choice.
    const visibleIds = tasks.map((task) => task.id);
    if (!(await loadLists())) return;
    if (listId && selectedRef.current === listId) {
      const refreshed =
        visibleIds.length === 0 ? await loadTasks(listId) : await refreshVisibleTasks(listId, visibleIds);
      if (!refreshed) return;
    }
    updates.acknowledge(seenVersion);
    setMessage(
      "Displayed tasks checked. Refresh tasks to see new tasks or return to the first page. Refresh open comments separately.",
    );
  }

  function closeEditor() {
    setCreating(false);
    setEditing(null);
  }

  function choose(row: List) {
    selectedRef.current = row.id;
    editorGeneration.current += 1;
    taskGeneration.current += 1;
    setSelected(row);
    setRename(row.title);
    setRenameConflict(false);
    setTasks([]);
    closeEditor();
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
    const renameGeneration = generation.current;
    const renameEditor = editorGeneration.current;
    const isCurrent = () =>
      renameGeneration === generation.current && renameEditor === editorGeneration.current;
    try {
      const result = await api<List>(`/todos/lists/${selected.id}`, {
        method: "PUT",
        body: { title: rename, revision: selected.revision },
      });
      if (!isCurrent()) return;
      setSelected(result);
      setLists((rows) => rows.map((row) => (row.id === result.id ? result : row)));
      setRenameConflict(false);
      setMessage("List renamed.");
    } catch (e: unknown) {
      if (isCurrent()) {
        failed(e);
        setRenameConflict(errorStatus(e) === 409);
      }
    } finally {
      setBusy(false);
    }
  }

  async function loadLatestList() {
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
      setLists((rows) => rows.map((existing) => (existing.id === row.id ? row : existing)));
    } catch (e: unknown) {
      failed(e);
    } finally {
      setBusy(false);
    }
  }

  function openNewTaskEditor() {
    setCreating(true);
    setEditing(null);
    editorGeneration.current += 1;
    setEditorKey(editorGeneration.current);
  }

  function openTaskEditor(task: Task) {
    setEditing(task);
    setCreating(false);
    editorGeneration.current += 1;
    setEditorKey(editorGeneration.current);
  }

  function cancelEditor() {
    editorGeneration.current += 1;
    closeEditor();
  }

  function editorSaved(listId: string) {
    if (editorGeneration.current !== editorKey) return;
    editorGeneration.current += 1;
    closeEditor();
    setMessage("Task saved.");
    void loadTasks(listId);
  }

  function reloadTasksIfStill(listId: string) {
    if (selectedRef.current === listId) void loadTasks(listId);
  }

  return {
    lists,
    listCursor,
    selected,
    tasks,
    taskCursor,
    title,
    setTitle,
    rename,
    setRename,
    error,
    message,
    busy,
    loading,
    taskLoading,
    creating,
    editing,
    editorKey,
    unconfirmed,
    renameConflict,
    updates,
    loadLists,
    loadTasks,
    refreshShared,
    choose,
    createList,
    renameList,
    loadLatestList,
    openNewTaskEditor,
    openTaskEditor,
    cancelEditor,
    editorSaved,
    reloadTasksIfStill,
  };
}

export type Todos = ReturnType<typeof useTodos>;
