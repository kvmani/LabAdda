import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { fmtTime, isoToLocal, localToIso } from "../format";

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
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
      </label>
      <label>
        Note
        <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
      </label>
      <div className="row wrap">
        <label className="inline">
          Due <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <label className="inline">
          Remind me <input type="datetime-local" value={remind} onChange={(e) => setRemind(e.target.value)} />
        </label>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button type="submit">{note ? "Save note" : "Add note"}</button>
        {onCancel && (
          <button type="button" className="ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

export function Notes() {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () =>
    api("/notes")
      .then((r) => setNotes(r.notes))
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  return (
    <section className="notes">
      <h1>My Notes</h1>
      <p className="muted">
        Only you can see these notes and reminders. They never appear in workspace search, colleague
        notifications or on shared panels.
      </p>
      <NoteForm onSaved={load} />
      {error && <p className="error">{error}</p>}
      {notes === null ? (
        <p className="muted">Loading…</p>
      ) : notes.length === 0 ? (
        <p className="state empty">No notes yet.</p>
      ) : (
        notes.map((n) =>
          editing === n.id ? (
            <NoteForm
              key={n.id}
              note={n}
              onSaved={() => {
                setEditing(null);
                load();
              }}
              onCancel={() => setEditing(null)}
            />
          ) : (
            <article key={n.id} className="card note">
              <div className="row between">
                <h2>{n.title || "Untitled"}</h2>
                <div className="row">
                  <button className="ghost small" onClick={() => setEditing(n.id)}>
                    Edit
                  </button>
                  <button
                    className="ghost small"
                    onClick={() =>
                      window.confirm("Delete this note?") &&
                      api(`/notes/${n.id}`, { method: "DELETE" }).then(load)
                    }
                  >
                    Delete
                  </button>
                </div>
              </div>
              <p className="body">{n.body}</p>
              {n.due_at && (
                <p className="due">
                  Due {fmtTime(n.due_at)}
                  {n.remind_at ? ` · reminder ${fmtTime(n.remind_at)}` : ""}
                </p>
              )}
            </article>
          ),
        )
      )}
    </section>
  );
}
