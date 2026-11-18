import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { invalidate } from "../../generation";
import type { Work } from "./useDashboardOverview";

type Status = "todo" | "in_progress" | "blocked" | "done";
type Task = {
  id: string;
  title: string;
  description: string;
  due_date: string | null;
  priority: "low" | "normal" | "high";
  checklist: { title: string; done: boolean }[];
  revision: number;
  status: Status;
  done: boolean;
};
type Notice = { title: string; listId: string; task: Task; previous: Status; workspaceId: string | null };
function edit(task: Task, status: Status) {
  return {
    title: task.title,
    description: task.description,
    due_date: task.due_date,
    priority: task.priority,
    checklist: task.checklist,
    revision: task.revision,
    status,
    done: status === "done",
  };
}

/** Confirm durable completion, and undo only the revision produced by that completion. */
export function useHomeTasks(refresh: () => Promise<void>, scopeKey: string) {
  const [pending, setPending] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const busy = useRef(false);
  useEffect(() => {
    invalidate(generation);
    setNotice(null);
    setPending(null);
    setError("");
    busy.current = false;
    return () => invalidate(generation);
  }, [scopeKey]);
  async function toggle(task: Work) {
    if (busy.current) return;
    busy.current = true;
    setPending(task.id);
    setError("");
    const token = ++generation.current;
    try {
      const url = `/todos/lists/${task.list_id}/tasks/${task.id}`;
      const current = await api<Task>(url);
      if (token !== generation.current) return;
      if (current.status === "done") {
        await refresh();
        return;
      }
      const saved = await api<Task>(url, { method: "PUT", body: edit(current, "done") });
      if (token !== generation.current) return;
      setNotice({
        title: saved.title,
        listId: task.list_id,
        task: saved,
        previous: current.status,
        workspaceId: task.workspace_id,
      });
      await refresh();
    } catch (failure: unknown) {
      if (token === generation.current) setError(errorMessage(failure));
    } finally {
      if (token === generation.current) {
        busy.current = false;
        setPending(null);
      }
    }
  }
  async function undo() {
    if (!notice || busy.current) return;
    busy.current = true;
    setPending(notice.task.id);
    setError("");
    const token = ++generation.current;
    try {
      await api(`/todos/lists/${notice.listId}/tasks/${notice.task.id}`, {
        method: "PUT",
        body: edit(notice.task, notice.previous),
      });
      if (token !== generation.current) return;
      setNotice(null);
      await refresh();
    } catch (failure: unknown) {
      if (token === generation.current) setError(errorMessage(failure));
    } finally {
      if (token === generation.current) {
        busy.current = false;
        setPending(null);
      }
    }
  }
  return { pending, notice, error, toggle, undo };
}
