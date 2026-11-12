import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import { fmtTime, isoToLocal, localToIso } from "../format";
import {
  Button,
  Card,
  ConfirmDialog,
  DateInput,
  EmptyState,
  ErrorState,
  PageHeader,
  Skeleton,
  TextArea,
  TextInput,
} from "../ui";
import "./notes.css";

type Note = {
  id: string;
  title: string;
  body: string;
  due_at: string | null;
  remind_at: string | null;
  updated_at: string;
};

function NoteForm({ note, onSaved, onCancel }: { note?: Note; onSaved: () => void; onCancel?: () => void }) {
  const [title, setTitle] = useState(note?.title ?? "");
  const [body, setBody] = useState(note?.body ?? "");
  const [due, setDue] = useState(isoToLocal(note?.due_at ?? null));
  const [remind, setRemind] = useState(isoToLocal(note?.remind_at ?? null));
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const payload = { title, body, due_at: localToIso(due), remind_at: localToIso(remind) };
      if (note) await api(`/notes/${note.id}`, { method: "PUT", body: payload });
      else await api("/notes", { body: payload });
      if (!note) {
        setTitle("");
        setBody("");
        setDue("");
        setRemind("");
      }
      onSaved();
    } catch (err: unknown) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card>
      <form className="notes__form" onSubmit={submit}>
        <TextInput label="Title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
        <TextArea label="Note" value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
        <div className="notes__dates">
          <DateInput kind="datetime-local" label="Due" value={due} onChange={(e) => setDue(e.target.value)} />
          <DateInput
            kind="datetime-local"
            label="Remind me"
            value={remind}
            onChange={(e) => setRemind(e.target.value)}
          />
        </div>
        {error && (
          <p className="notes__error" role="alert">
            {error}
          </p>
        )}
        <div className="notes__row">
          {onCancel && (
            <Button variant="quiet" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button variant="primary" type="submit">
            {note ? "Save note" : "Add note"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function Notes() {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [removing, setRemoving] = useState<Note | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () =>
    api<{ notes: Note[] }>("/notes")
      .then((r) => {
        setNotes(r.notes);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    void load();
  }, []);

  async function remove() {
    if (!removing) return;
    await api(`/notes/${removing.id}`, { method: "DELETE" });
    setRemoving(null);
    await load();
  }

  return (
    <section className="notes">
      <PageHeader
        title="My Notes"
        scope="Only you can see these notes and reminders. They never appear in workspace search, colleague notifications or on shared panels."
      />
      <NoteForm onSaved={load} />
      {error && (
        <ErrorState message={error} title="Your notes could not be loaded" onRetry={() => void load()} />
      )}
      {notes === null && !error && <Skeleton lines={3} label="Loading…" />}
      {notes?.length === 0 && (
        <EmptyState title="No notes yet.">Write your first private note above.</EmptyState>
      )}
      {notes?.map((n) =>
        editing === n.id ? (
          <NoteForm
            key={n.id}
            note={n}
            onSaved={() => {
              setEditing(null);
              void load();
            }}
            onCancel={() => setEditing(null)}
          />
        ) : (
          <article key={n.id} className="note">
            <Card
              title={n.title || "Untitled"}
              actions={
                <>
                  <Button variant="quiet" size="sm" onClick={() => setEditing(n.id)}>
                    Edit
                  </Button>
                  <Button variant="quiet" size="sm" onClick={() => setRemoving(n)}>
                    Delete
                  </Button>
                </>
              }
            >
              <div className="notes__form">
                <p className="notes__body">{n.body}</p>
                {n.due_at && (
                  <p className="notes__due">
                    Due {fmtTime(n.due_at)}
                    {n.remind_at ? ` · reminder ${fmtTime(n.remind_at)}` : ""}
                  </p>
                )}
              </div>
            </Card>
          </article>
        ),
      )}
      <ConfirmDialog
        open={removing !== null}
        title="Delete this note"
        consequences={["The note is removed from My Notes. Only you could see it."]}
        confirmLabel="Delete note"
        onConfirm={remove}
        onCancel={() => setRemoving(null)}
        danger
      />
    </section>
  );
}
