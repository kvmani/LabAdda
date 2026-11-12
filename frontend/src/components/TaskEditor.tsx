import { useRef, useState, type FormEvent } from "react";
import { api, errorMessage, errorStatus, outcomeUnknown } from "../api";
import type { Assignee } from "./TaskAssignment";
import { Button, Card, Checkbox, DateInput, Select, TextArea, TextInput } from "../ui";
import "./task-editor.css";

export type Workflow = "todo" | "in_progress" | "blocked" | "done";
export const workflowLabels: Record<Workflow, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done",
};
export type Fields = {
  status: Workflow;
  title: string;
  description: string;
  due_date: string | null;
  priority: string;
  checklist: { title: string; done: boolean }[];
  done: boolean;
};
export type Task = Fields & { has_source: boolean; assignee: Assignee | null; id: string; revision: number };
export type Page<T> = { items: T[]; next_cursor: string | null };
const blank = (): Fields => ({
  status: "todo",
  title: "",
  description: "",
  due_date: null,
  priority: "normal",
  checklist: [],
  done: false,
});

export function TaskEditor({
  listId,
  initial,
  saved,
  cancel,
}: {
  listId: string;
  initial: Task | null;
  saved: () => void;
  cancel: () => void;
}) {
  const [fields, setFields] = useState<Fields>(initial ?? blank());
  const [revision, setRevision] = useState(initial?.revision ?? 1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState(false);
  const [conflict, setConflict] = useState(false);
  const attempt = useRef<({ client_id: string } & Fields) | null>(null);
  const path = `/todos/lists/${listId}/tasks`;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setConflict(false);
    try {
      if (initial) {
        const { title, description, due_date, priority, checklist, done, status } = fields;
        await api(`${path}/${initial.id}`, {
          method: "PUT",
          body: { title, description, due_date, priority, checklist, done, status, revision },
        });
      } else {
        attempt.current ??= { ...fields, client_id: crypto.randomUUID() };
        await api(path, { body: attempt.current });
      }
      saved();
    } catch (e: unknown) {
      setError(errorMessage(e));
      setConflict(errorStatus(e) === 409);
      if (!initial) {
        setUnconfirmed(outcomeUnknown(e));
        if (!outcomeUnknown(e)) attempt.current = null;
      }
    } finally {
      setBusy(false);
    }
  }
  async function latest() {
    setBusy(true);
    setError("");
    try {
      const result = await api<Task>(`${path}/${initial!.id}`);
      setFields(result);
      setRevision(result.revision);
      setConflict(false);
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const blankChecklist = fields.checklist.some((item) => !item.title.trim());
  const setItem = (index: number, change: Partial<Fields["checklist"][number]>) =>
    setFields({
      ...fields,
      checklist: fields.checklist.map((v, i) => (i === index ? { ...v, ...change } : v)),
    });
  return (
    <Card title={initial ? "Edit task" : "New task"} level={3}>
      <form onSubmit={submit} className="task-editor">
        <fieldset disabled={busy || unconfirmed} className="task-editor__fields">
          <TextInput
            label="Task title"
            maxLength={200}
            value={fields.title}
            onChange={(e) => setFields({ ...fields, title: e.target.value })}
          />
          <TextArea
            label="Description"
            maxLength={10000}
            value={fields.description}
            onChange={(e) => setFields({ ...fields, description: e.target.value })}
          />
          <div className="task-editor__row">
            <DateInput
              label="Due date"
              value={fields.due_date ?? ""}
              onChange={(e) => setFields({ ...fields, due_date: e.target.value || null })}
            />
            <Select
              label="Priority"
              value={fields.priority}
              onChange={(e) => setFields({ ...fields, priority: e.target.value })}
              options={["low", "normal", "high"].map((p) => ({ value: p, label: p }))}
            />
            <Select
              label="Workflow state"
              value={fields.status}
              onChange={(e) => {
                const status = e.target.value as Workflow;
                setFields({ ...fields, status, done: status === "done" });
              }}
              options={Object.entries(workflowLabels).map(([value, label]) => ({ value, label }))}
            />
          </div>
          <Checkbox
            label="Task completed"
            checked={fields.done}
            onChange={(e) =>
              setFields({ ...fields, done: e.target.checked, status: e.target.checked ? "done" : "todo" })
            }
          />
          <h4 className="task-editor__heading">Checklist</h4>
          {fields.checklist.map((item, index) => (
            <div className="task-editor__item" key={index}>
              <Checkbox
                label={`Checklist item ${index + 1} done`}
                checked={item.done}
                onChange={(e) => setItem(index, { done: e.target.checked })}
              />
              <TextInput
                label={`Checklist item ${index + 1} title`}
                maxLength={200}
                value={item.title}
                onChange={(e) => setItem(index, { title: e.target.value })}
              />
              <Button
                variant="quiet"
                size="sm"
                onClick={() =>
                  setFields({ ...fields, checklist: fields.checklist.filter((_, i) => i !== index) })
                }
              >
                Remove item {index + 1}
              </Button>
            </div>
          ))}
          <div>
            <Button
              icon="plus"
              disabled={fields.checklist.length >= 50}
              onClick={() =>
                setFields({ ...fields, checklist: [...fields.checklist, { title: "", done: false }] })
              }
            >
              Add checklist item
            </Button>
          </div>
        </fieldset>
        {error && (
          <p role="alert" className="task__error">
            {error}
          </p>
        )}
        {unconfirmed && (
          <p role="status">
            Creation is unconfirmed. Retry the same request to recover its result; these fields are kept
            unchanged.
          </p>
        )}
        {conflict && <p>Your draft is kept. Copy any changes you need before loading the latest task.</p>}
        {conflict && initial && (
          <div>
            <Button disabled={busy} onClick={latest}>
              Load latest task (replaces draft)
            </Button>
          </div>
        )}
        <div className="task-actions">
          <Button variant="quiet" disabled={busy} onClick={cancel}>
            Close editor
          </Button>
          <Button
            variant="primary"
            type="submit"
            busy={busy}
            busyLabel="Saving…"
            disabled={!fields.title.trim() || blankChecklist}
          >
            {unconfirmed ? "Retry same task creation" : "Save task"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
