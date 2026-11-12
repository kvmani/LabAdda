import { useEffect, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { Link } from "react-router-dom";
import { accessDenied, api, errorCode, errorMessage, outcomeUnknown } from "../api";
import { realtime } from "../realtime";
import { useWorkspaces } from "../workspaces";
import type { Workspace } from "../types";
import { Button, Checkbox, Dialog, Select, TextArea, TextInput } from "../ui";
import "./conversation-task.css";

type List = { id: string; title: string };
type Page = { items: List[]; next_cursor: string | null };
type Context = { epoch: number; revision: number };
type SourceIntent =
  | { source_kind: "post" | "chat"; source_id: string }
  | { source_workspace_id: string; source_epoch: number; source_revision: number };
type Intent = {
  listId: string;
  endpoint: "from-board" | "from-conversation";
  body: { client_id: string; title: string; description: string; confirm_audience: boolean } & SourceIntent;
};
type Props = { source: Workspace; text: string; close: () => void } & (
  | { kind: "post" | "chat"; sourceId: string; boardContext?: never }
  | { kind: "board"; sourceId?: never; boardContext: Context }
);

/** The user reviews a copy. Source references never broaden source permissions. */
export function ConversationTask({ source, kind, sourceId, text, close, boardContext }: Props) {
  const { workspaces } = useWorkspaces();
  const [context, setContext] = useState(boardContext),
    [needsContext, setNeedsContext] = useState(false);
  const formLabel = kind === "board" ? "Create task from board" : "Create task from conversation";
  const sourceLabel = kind === "board" ? "board" : "conversation";
  const [destination, setDestination] = useState(
    source.can_write && !source.archived ? source.id : "personal",
  );
  const [lists, setLists] = useState<Page | null>(null),
    [listId, setListId] = useState("");
  const [title, setTitle] = useState((text.trim().split("\n")[0] ?? "").slice(0, 200)),
    [description, setDescription] = useState(text.slice(0, 10000));
  const [confirmed, setConfirmed] = useState(false),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false);
  const [unknown, setUnknown] = useState(false),
    [blocked, setBlocked] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  const generation = useRef(0),
    attempt = useRef<Intent | null>(null);
  const target = workspaces.find((w) => w.id === destination),
    broader = destination !== "personal" && destination !== source.id;
  const writable = destination === "personal" || (!!target?.can_write && !target.archived);
  const location = destination === "personal" ? "/todos" : `/w/${destination}/todos`;
  function deny() {
    ++generation.current;
    setBlocked(true);
    setTitle("");
    setDescription("");
    setLists(null);
    setListId("");
    attempt.current = null;
    setBusy(false);
    setLoading(false);
    setUnknown(false);
  }
  useEffect(() => {
    let active = true;
    const unsubs = [...new Set([source.id, ...(destination === "personal" ? [] : [destination])])].map((id) =>
      realtime.subscribe(id, (event) => {
        if (active && ["revoked", "subscribe_failed", "session_ended"].includes(event.type)) deny();
      }),
    );
    return () => {
      active = false;
      invalidate(generation);
      unsubs.forEach((stop) => stop());
    };
  }, [source.id, destination]);
  async function load(after?: string) {
    const token = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const page = await api<Page>("/todos/lists", {
        params: { workspace_id: destination === "personal" ? undefined : destination, after },
      });
      if (token === generation.current) setLists(page);
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        if (accessDenied(e)) deny();
      }
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }
  useEffect(() => {
    setLists(null);
    setListId("");
    setConfirmed(false);
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload lists only when the chosen destination changes
  }, [destination]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || blocked || saved || needsContext || !writable || !listId || (broader && !confirmed)) return;
    const token = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const provenance: SourceIntent =
        kind === "board"
          ? {
              source_workspace_id: source.id,
              source_epoch: context!.epoch,
              source_revision: context!.revision,
            }
          : { source_kind: kind, source_id: sourceId };
      attempt.current ??= {
        listId,
        endpoint: kind === "board" ? "from-board" : "from-conversation",
        body: {
          client_id: crypto.randomUUID(),
          title,
          description,
          confirm_audience: confirmed,
          ...provenance,
        },
      };
      await api(`/todos/lists/${attempt.current.listId}/${attempt.current.endpoint}`, {
        body: attempt.current.body,
      });
      if (token !== generation.current) return;
      setSaved(true);
      setUnknown(false);
      attempt.current = null;
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        if (errorCode(e) === "board_context_changed") setNeedsContext(true);
        const uncertain = outcomeUnknown(e);
        setUnknown(uncertain);
        if (!uncertain) attempt.current = null;
        if (accessDenied(e)) deny();
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }
  async function latestContext() {
    if (busy || unknown || loading) return;
    const token = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const latest = await api<Context>(`/todos/board-context/${source.id}`);
      if (token !== generation.current) return;
      setContext(latest);
      setNeedsContext(false);
      setConfirmed(false);
      attempt.current = null;
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        if (accessDenied(e)) deny();
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }
  const heading = `Create task from ${
    kind === "board" ? "research plan board" : kind === "post" ? "post" : "chat message"
  }`;
  const closeButton = (
    <Button variant="quiet" disabled={busy} onClick={close}>
      Close task creation
    </Button>
  );
  if (blocked)
    return (
      <Dialog open title={heading} onClose={close} size="sm" footer={closeButton}>
        <section aria-label={formLabel}>
          <p role="alert">
            The source or destination is no longer available. Reopen it after checking access.
          </p>
        </section>
      </Dialog>
    );
  if (saved)
    return (
      <Dialog open title={heading} onClose={close} size="sm" footer={closeButton}>
        <section className="conversation-task__done" aria-label={formLabel}>
          <p role="status">
            Task saved. Its source link still requires access to the original {sourceLabel}.
          </p>
          <Link to={location}>Open destination tasks</Link>
        </section>
      </Dialog>
    );
  const submitLabel = busy
    ? "Saving…"
    : unknown
      ? "Retry same task copy"
      : kind === "board"
        ? "Save board task"
        : "Save conversation task";
  return (
    <Dialog open title={heading} onClose={close}>
      <form className="conversation-task" aria-label={formLabel} onSubmit={submit}>
        <p className="conversation-task__intro">
          {kind === "board"
            ? "Describe the followup and review its destination. This records board context, without copying an image or board content."
            : "Review the copied text and destination before saving. Later conversation changes do not update this task copy."}
        </p>
        <fieldset disabled={busy || unknown} className="conversation-task__fields">
          {kind === "board" && context && (
            <>
              <p>
                Reviewed board context: epoch {context.epoch}, revision {context.revision}. The reference
                opens the live board; it is not a saved image.
              </p>
              {needsContext && (
                <p role="status">
                  Your task draft is kept. Review the board, then load its latest context before saving.
                </p>
              )}
              <div>
                <Button disabled={loading} onClick={latestContext}>
                  Load latest board context (keeps draft)
                </Button>
              </div>
            </>
          )}
          <Select
            label="Task destination"
            value={destination}
            onChange={(e) => {
              ++generation.current;
              setDestination(e.target.value);
              setLists(null);
              setListId("");
              setConfirmed(false);
            }}
            options={[
              { value: "personal", label: "My personal lists (private)" },
              ...workspaces
                .filter((w) => w.can_write && !w.archived)
                .map((w) => ({ value: w.id, label: w.name })),
            ]}
          />
          <p className="conversation-task__audience">
            {destination === "personal"
              ? "Audience: only you."
              : `Audience: everyone who can read ${target?.name ?? "the selected workspace"}.`}
          </p>
          {loading && <p role="status">Loading destination lists…</p>}
          {lists && (
            <Select
              label="Destination list"
              placeholder="Choose a list"
              value={listId}
              onChange={(e) => {
                setListId(e.target.value);
                setConfirmed(false);
              }}
              options={lists.items.map((row) => ({ value: row.id, label: row.title }))}
            />
          )}
          {lists?.items.length === 0 && (
            <p>Create a to-do list in the destination first, then reopen this form.</p>
          )}
          <div className="conversation-task__row">
            <Button
              disabled={loading}
              onClick={() => {
                setListId("");
                setConfirmed(false);
                void load();
              }}
            >
              Refresh destination lists
            </Button>
            {lists?.next_cursor && (
              <Button
                disabled={loading}
                onClick={() => {
                  setListId("");
                  setConfirmed(false);
                  void load(lists.next_cursor!);
                }}
              >
                More destination lists
              </Button>
            )}
          </div>
          <TextInput
            label="Task title"
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <TextArea
            label="Task description"
            maxLength={10000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          {broader && (
            <Checkbox
              label={`I confirm this reviewed task text will be shared with a different audience in ${target?.name}.`}
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
          )}
        </fieldset>
        {error && (
          <p role="alert" className="conversation-task__error">
            {error}
          </p>
        )}
        {unknown && (
          <p role="status">
            Creation is unconfirmed. Retry the same task copy; the original destination and text are kept
            unchanged.
          </p>
        )}
        <div className="conversation-task__actions">
          {closeButton}
          <Button
            variant="primary"
            type="submit"
            disabled={
              busy ||
              loading ||
              blocked ||
              needsContext ||
              !writable ||
              !listId ||
              !title.trim() ||
              (broader && !confirmed)
            }
          >
            {submitLabel}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
