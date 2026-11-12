import { useEffect, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { Button, Select, TextInput } from "../ui";
import "./task.css";
import { api, errorMessage, errorStatus, outcomeUnknown } from "../api";

export type Assignee = { id: string; display_name: string; is_active: boolean };
type Colleague = { id: string; display_name: string; username: string };
type Page = { items: Colleague[]; next_cursor: string | null };
type AssignmentProps = {
  listId: string;
  taskId: string;
  revision: number;
  assignee: Assignee | null;
  writable: boolean;
  saved: () => void;
};

/** State and requests for the assignee picker; every response is checked against a generation counter. */
function useAssignmentPicker({ listId, taskId, revision, assignee, saved }: AssignmentProps) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState<Page | null>(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(assignee?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [reloadNeeded, setReloadNeeded] = useState(false);
  const generation = useRef(0);
  const [draftRevision, setDraftRevision] = useState(revision);

  useEffect(() => {
    generation.current += 1;
    setOpen(false);
    setPage(null);
    setSelected(assignee?.id ?? "");
    setError("");
    setReloadNeeded(false);
    return () => {
      invalidate(generation);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset only when another task is shown; reads the assignee at that moment
  }, [listId, taskId]);

  useEffect(() => {
    if (open) setReloadNeeded(true);
    else setSelected(assignee?.id ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- react only to a new task revision; reads the open state at that moment
  }, [revision]);

  function close() {
    generation.current += 1;
    setOpen(false);
    setPage(null);
  }

  async function load(after?: string) {
    if (!open) {
      setDraftRevision(revision);
      setSelected(assignee?.id ?? "");
      setReloadNeeded(false);
    }
    generation.current += 1;
    const token = generation.current;
    setOpen(true);
    setLoading(true);
    setPage(null);
    setError("");
    try {
      const result = await api<Page>(`/todos/lists/${listId}/assignees`, { params: { q: query, after } });
      if (token === generation.current) setPage(result);
    } catch (e: unknown) {
      if (token === generation.current) setError(errorMessage(e));
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }

  async function assign(event: FormEvent) {
    event.preventDefault();
    if (busy || reloadNeeded) return;
    generation.current += 1;
    const token = generation.current;
    setBusy(true);
    setError("");
    try {
      await api(`/todos/lists/${listId}/tasks/${taskId}/assignee`, {
        method: "PUT",
        body: { user_id: selected || null, revision: draftRevision },
      });
      if (token === generation.current) {
        setOpen(false);
        setPage(null);
        saved();
      }
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        setReloadNeeded(outcomeUnknown(e) || errorStatus(e) === 409);
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }

  async function reload() {
    generation.current += 1;
    const token = generation.current;
    setBusy(true);
    setError("");
    try {
      const current = await api<{ assignee: Assignee | null }>(`/todos/lists/${listId}/tasks/${taskId}`);
      if (token !== generation.current) return;
      setSelected(current.assignee?.id ?? "");
      setReloadNeeded(false);
      setOpen(false);
      setPage(null);
      saved();
    } catch (e: unknown) {
      if (token === generation.current) setError(errorMessage(e));
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }

  return {
    open,
    page,
    query,
    setQuery,
    selected,
    setSelected,
    busy,
    loading,
    error,
    reloadNeeded,
    load,
    assign,
    reload,
    close,
  };
}

type Picker = ReturnType<typeof useAssignmentPicker>;

function assigneeOptions(assignee: Assignee | null, candidates: Colleague[]) {
  const currentIsListed = assignee && candidates.some((person) => person.id === assignee.id);
  const current =
    assignee && !currentIsListed
      ? [{ value: assignee.id, label: `${assignee.display_name} (current; eligibility must be checked)` }]
      : [];
  return [
    { value: "", label: "Unassigned" },
    ...current,
    ...candidates.map((person) => ({
      value: person.id,
      label: `${person.display_name} (${person.username})`,
    })),
  ];
}

function ColleagueSearch({ picker }: { picker: Picker }) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void picker.load();
      }}
    >
      <TextInput
        label="Find eligible colleague"
        maxLength={100}
        disabled={picker.busy}
        value={picker.query}
        onChange={(e) => picker.setQuery(e.target.value)}
      />
      <Button size="sm" disabled={picker.busy || picker.loading} type="submit">
        Search colleagues
      </Button>
    </form>
  );
}

function AssignmentForm({
  picker,
  assignee,
  page,
}: {
  picker: Picker;
  assignee: Assignee | null;
  page: Page;
}) {
  const locked = picker.busy || picker.reloadNeeded;
  return (
    <form onSubmit={picker.assign}>
      <Select
        label="Assignee"
        value={picker.selected}
        disabled={locked}
        onChange={(e) => picker.setSelected(e.target.value)}
        options={assigneeOptions(assignee, page.items)}
      />
      <Button size="sm" variant="primary" type="submit" disabled={locked}>
        Save assignment
      </Button>
    </form>
  );
}

function ReloadNotice({ picker }: { picker: Picker }) {
  return (
    <>
      <p>
        The task changed or the result is unconfirmed. Reload the current task before trying again; this
        discards your assignment choice.
      </p>
      <Button size="sm" disabled={picker.busy} onClick={picker.reload}>
        Reload task assignment
      </Button>
    </>
  );
}

export function TaskAssignment(props: AssignmentProps) {
  const { assignee, writable } = props;
  const picker = useAssignmentPicker(props);
  const { open, page } = picker;
  return (
    <section className="task-panel" aria-label="Task assignment">
      <p>
        Assignee:{" "}
        {assignee ? assignee.display_name + (assignee.is_active ? "" : " (inactive)") : "Unassigned"}
      </p>
      {writable && !open && (
        <Button size="sm" onClick={() => picker.load()}>
          Change assignee
        </Button>
      )}
      {writable && open && (
        <>
          <p>Assignment does not grant access. Choose an eligible colleague or leave the task unassigned.</p>
          <ColleagueSearch picker={picker} />
          {picker.loading && <p role="status">Loading eligible colleagues…</p>}
          {picker.error && (
            <p className="task__error" role="alert">
              {picker.error}
            </p>
          )}
          {page && <AssignmentForm picker={picker} assignee={assignee} page={page} />}
          {page?.next_cursor && (
            <Button size="sm" disabled={picker.busy} onClick={() => picker.load(page.next_cursor!)}>
              More colleagues
            </Button>
          )}
          {picker.reloadNeeded && <ReloadNotice picker={picker} />}
          <Button size="sm" disabled={picker.busy} onClick={picker.close}>
            Close assignment
          </Button>
        </>
      )}
    </section>
  );
}
