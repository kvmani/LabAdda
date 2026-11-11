import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, errorMessage, errorStatus, outcomeUnknown } from "../api";

export type Assignee = { id: string; display_name: string; is_active: boolean };
type Colleague = { id: string; display_name: string; username: string };
type Page = { items: Colleague[]; next_cursor: string | null };
export function TaskAssignment({
  listId,
  taskId,
  revision,
  assignee,
  writable,
  saved,
}: {
  listId: string;
  taskId: string;
  revision: number;
  assignee: Assignee | null;
  writable: boolean;
  saved: () => void;
}) {
  const [open, setOpen] = useState(false),
    [page, setPage] = useState<Page | null>(null);
  const [query, setQuery] = useState(""),
    [selected, setSelected] = useState(assignee?.id ?? "");
  const [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const [reloadNeeded, setReloadNeeded] = useState(false);
  const generation = useRef(0);
  const [draftRevision, setDraftRevision] = useState(revision);
  useEffect(() => {
    ++generation.current;
    setOpen(false);
    setPage(null);
    setSelected(assignee?.id ?? "");
    setError("");
    setReloadNeeded(false);
    return () => {
      ++generation.current;
    };
  }, [listId, taskId]);
  useEffect(() => {
    if (open) setReloadNeeded(true);
    else setSelected(assignee?.id ?? "");
  }, [revision]);
  async function load(after?: string) {
    if (!open) {
      setDraftRevision(revision);
      setSelected(assignee?.id ?? "");
      setReloadNeeded(false);
    }
    const token = ++generation.current;
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
    const token = ++generation.current;
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
    const token = ++generation.current;
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
  return (
    <section aria-label="Task assignment">
      <p>
        Assignee:{" "}
        {assignee ? assignee.display_name + (assignee.is_active ? "" : " (inactive)") : "Unassigned"}
      </p>
      {writable && !open && (
        <button type="button" onClick={() => load()}>
          Change assignee
        </button>
      )}
      {writable && open && (
        <>
          <p>Assignment does not grant access. Choose an eligible colleague or leave the task unassigned.</p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              load();
            }}
          >
            <label>
              Find eligible colleague
              <input
                maxLength={100}
                disabled={busy}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <button disabled={busy || loading} type="submit">
              Search colleagues
            </button>
          </form>
          {loading && <p role="status">Loading eligible colleagues…</p>}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {page && (
            <form onSubmit={assign}>
              <label>
                Assignee
                <select
                  aria-label="Assignee"
                  value={selected}
                  disabled={busy || reloadNeeded}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  <option value="">Unassigned</option>
                  {assignee && !page.items.some((r) => r.id === assignee.id) && (
                    <option value={assignee.id}>
                      {assignee.display_name} (current; eligibility must be checked)
                    </option>
                  )}
                  {page.items.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.display_name} ({person.username})
                    </option>
                  ))}
                </select>
              </label>
              <button type="submit" disabled={busy || reloadNeeded}>
                Save assignment
              </button>
            </form>
          )}
          {page?.next_cursor && (
            <button type="button" disabled={busy} onClick={() => load(page.next_cursor!)}>
              More colleagues
            </button>
          )}
          {reloadNeeded && (
            <p>
              The task changed or the result is unconfirmed. Reload the current task before trying again; this
              discards your assignment choice.
            </p>
          )}
          {reloadNeeded && (
            <button type="button" disabled={busy} onClick={reload}>
              Reload task assignment
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              ++generation.current;
              setOpen(false);
              setPage(null);
            }}
          >
            Close assignment
          </button>
        </>
      )}
    </section>
  );
}
