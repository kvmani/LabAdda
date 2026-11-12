import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
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

const DENIAL_EVENTS = ["revoked", "subscribe_failed", "session_ended"];

function headingFor(kind: Props["kind"]): string {
  if (kind === "board") return "Create task from research plan board";
  return kind === "post" ? "Create task from post" : "Create task from chat message";
}

function submitLabelFor(kind: Props["kind"], busy: boolean, unknown: boolean): string {
  if (busy) return "Saving…";
  if (unknown) return "Retry same task copy";
  return kind === "board" ? "Save board task" : "Save conversation task";
}

/** Where the task will come from, as the server records it. */
function provenanceOf(props: Props, context: Context | undefined): SourceIntent {
  if (props.kind === "board") {
    return {
      source_workspace_id: props.source.id,
      source_epoch: context!.epoch,
      source_revision: context!.revision,
    };
  }
  return { source_kind: props.kind, source_id: props.sourceId };
}

/**
 * Draft, destination and save state for turning a conversation or board into a task copy.
 * Every request is numbered; a response from an earlier number, or after access was lost, is dropped.
 */
function useConversationTask(props: Props) {
  const { source, kind, text, boardContext } = props;
  const { workspaces } = useWorkspaces();
  const [context, setContext] = useState(boardContext);
  const [needsContext, setNeedsContext] = useState(false);
  const [destination, setDestination] = useState(
    source.can_write && !source.archived ? source.id : "personal",
  );
  const [lists, setLists] = useState<Page | null>(null);
  const [listId, setListId] = useState("");
  const [title, setTitle] = useState((text.trim().split("\n")[0] ?? "").slice(0, 200));
  const [description, setDescription] = useState(text.slice(0, 10000));
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const generation = useRef(0);
  const attempt = useRef<Intent | null>(null);
  const target = workspaces.find((workspace) => workspace.id === destination);
  const broader = destination !== "personal" && destination !== source.id;
  const writable = destination === "personal" || (!!target?.can_write && !target.archived);

  function deny() {
    generation.current += 1;
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
    const watchedIds = [...new Set([source.id, ...(destination === "personal" ? [] : [destination])])];
    const unsubscribers = watchedIds.map((id) =>
      realtime.subscribe(id, (event) => {
        if (active && DENIAL_EVENTS.includes(event.type)) deny();
      }),
    );
    return () => {
      active = false;
      invalidate(generation);
      unsubscribers.forEach((stop) => stop());
    };
  }, [source.id, destination]);

  async function load(after?: string) {
    generation.current += 1;
    const token = generation.current;
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

  function chooseDestination(nextDestination: string) {
    generation.current += 1;
    setDestination(nextDestination);
    setLists(null);
    setListId("");
    setConfirmed(false);
  }

  function chooseList(nextListId: string) {
    setListId(nextListId);
    setConfirmed(false);
  }

  function reloadLists(after?: string) {
    chooseList("");
    void load(after);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || blocked || saved || needsContext || !writable || !listId || (broader && !confirmed)) return;
    generation.current += 1;
    const token = generation.current;
    setBusy(true);
    setError("");
    try {
      attempt.current ??= {
        listId,
        endpoint: kind === "board" ? "from-board" : "from-conversation",
        body: {
          client_id: crypto.randomUUID(),
          title,
          description,
          confirm_audience: confirmed,
          ...provenanceOf(props, context),
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

  async function loadLatestContext() {
    if (busy || unknown || loading) return;
    generation.current += 1;
    const token = generation.current;
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

  return {
    context,
    needsContext,
    destination,
    lists,
    listId,
    title,
    setTitle,
    description,
    setDescription,
    confirmed,
    setConfirmed,
    busy,
    loading,
    unknown,
    blocked,
    error,
    saved,
    target,
    broader,
    writable,
    chooseDestination,
    chooseList,
    reloadLists,
    submit,
    loadLatestContext,
  };
}

type Draft = ReturnType<typeof useConversationTask>;

function BoardContextNotice({ draft, context }: { draft: Draft; context: Context }) {
  return (
    <>
      <p>
        Reviewed board context: epoch {context.epoch}, revision {context.revision}. The reference opens the
        live board; it is not a saved image.
      </p>
      {draft.needsContext && (
        <p role="status">
          Your task draft is kept. Review the board, then load its latest context before saving.
        </p>
      )}
      <div>
        <Button disabled={draft.loading} onClick={draft.loadLatestContext}>
          Load latest board context (keeps draft)
        </Button>
      </div>
    </>
  );
}

function DestinationFields({ draft }: { draft: Draft }) {
  const { workspaces } = useWorkspaces();
  const { lists, loading, target } = draft;
  return (
    <>
      <Select
        label="Task destination"
        value={draft.destination}
        onChange={(e) => draft.chooseDestination(e.target.value)}
        options={[
          { value: "personal", label: "My personal lists (private)" },
          ...workspaces
            .filter((workspace) => workspace.can_write && !workspace.archived)
            .map((workspace) => ({ value: workspace.id, label: workspace.name })),
        ]}
      />
      <p className="conversation-task__audience">
        {draft.destination === "personal"
          ? "Audience: only you."
          : `Audience: everyone who can read ${target?.name ?? "the selected workspace"}.`}
      </p>
      {loading && <p role="status">Loading destination lists…</p>}
      {lists && (
        <Select
          label="Destination list"
          placeholder="Choose a list"
          value={draft.listId}
          onChange={(e) => draft.chooseList(e.target.value)}
          options={lists.items.map((row) => ({ value: row.id, label: row.title }))}
        />
      )}
      {lists?.items.length === 0 && (
        <p>Create a to-do list in the destination first, then reopen this form.</p>
      )}
      <div className="conversation-task__row">
        <Button disabled={loading} onClick={() => draft.reloadLists()}>
          Refresh destination lists
        </Button>
        {lists?.next_cursor && (
          <Button disabled={loading} onClick={() => draft.reloadLists(lists.next_cursor!)}>
            More destination lists
          </Button>
        )}
      </div>
    </>
  );
}

function TextFields({ draft }: { draft: Draft }) {
  return (
    <>
      <TextInput
        label="Task title"
        maxLength={200}
        value={draft.title}
        onChange={(e) => draft.setTitle(e.target.value)}
      />
      <TextArea
        label="Task description"
        maxLength={10000}
        value={draft.description}
        onChange={(e) => draft.setDescription(e.target.value)}
      />
      {draft.broader && (
        <Checkbox
          label={`I confirm this reviewed task text will be shared with a different audience in ${draft.target?.name}.`}
          checked={draft.confirmed}
          onChange={(e) => draft.setConfirmed(e.target.checked)}
        />
      )}
    </>
  );
}

function ReviewForm({
  draft,
  kind,
  closeButton,
}: {
  draft: Draft;
  kind: Props["kind"];
  closeButton: ReactNode;
}) {
  const { busy, unknown, context } = draft;
  const formLabel = kind === "board" ? "Create task from board" : "Create task from conversation";
  const cannotSave =
    busy ||
    draft.loading ||
    draft.blocked ||
    draft.needsContext ||
    !draft.writable ||
    !draft.listId ||
    !draft.title.trim() ||
    (draft.broader && !draft.confirmed);
  return (
    <form className="conversation-task" aria-label={formLabel} onSubmit={draft.submit}>
      <p className="conversation-task__intro">
        {kind === "board"
          ? "Describe the followup and review its destination. This records board context, without copying an image or board content."
          : "Review the copied text and destination before saving. Later conversation changes do not update this task copy."}
      </p>
      <fieldset disabled={busy || unknown} className="conversation-task__fields">
        {kind === "board" && context && <BoardContextNotice draft={draft} context={context} />}
        <DestinationFields draft={draft} />
        <TextFields draft={draft} />
      </fieldset>
      {draft.error && (
        <p role="alert" className="conversation-task__error">
          {draft.error}
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
        <Button variant="primary" type="submit" disabled={cannotSave}>
          {submitLabelFor(kind, busy, unknown)}
        </Button>
      </div>
    </form>
  );
}

/** The user reviews a copy. Source references never broaden source permissions. */
export function ConversationTask(props: Props) {
  const { kind, close } = props;
  const draft = useConversationTask(props);
  const heading = headingFor(kind);
  const formLabel = kind === "board" ? "Create task from board" : "Create task from conversation";
  const sourceLabel = kind === "board" ? "board" : "conversation";
  const location = draft.destination === "personal" ? "/todos" : `/w/${draft.destination}/todos`;
  const closeButton = (
    <Button variant="quiet" disabled={draft.busy} onClick={close}>
      Close task creation
    </Button>
  );
  if (draft.blocked) {
    return (
      <Dialog open title={heading} onClose={close} size="sm" footer={closeButton}>
        <section aria-label={formLabel}>
          <p role="alert">
            The source or destination is no longer available. Reopen it after checking access.
          </p>
        </section>
      </Dialog>
    );
  }
  if (draft.saved) {
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
  }
  return (
    <Dialog open title={heading} onClose={close}>
      <ReviewForm draft={draft} kind={kind} closeButton={closeButton} />
    </Dialog>
  );
}
