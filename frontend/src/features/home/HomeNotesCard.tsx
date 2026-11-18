import { useState, type FormEvent, type RefObject } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api";
import { Skeleton } from "../../ui";
import type { PersonalNote, useHomePanels } from "./useHomePanels";
const NOTE_TAGS = [
  { label: "Idea", icon: "💡", prefix: "[Idea] " },
  { label: "Experiment", icon: "🔬", prefix: "[Experiment] " },
  { label: "Reminder", icon: "📌", prefix: "[Reminder] " },
  { label: "Paper", icon: "📖", prefix: "[Paper] " },
];

type Props = {
  panels: Pick<ReturnType<typeof useHomePanels>, "notes" | "notesLoading" | "notesError" | "addNote">;
  noteInputRef: RefObject<HTMLInputElement>;
};
export function HomeNotesCard({ panels, noteInputRef }: Props) {
  const { notes, notesLoading, notesError, addNote } = panels;
  const [quickNoteError, setQuickNoteError] = useState("");

  const [quickNoteTitle, setQuickNoteTitle] = useState("");
  const [quickNoteSaving, setQuickNoteSaving] = useState(false);
  const [quickNoteSuccess, setQuickNoteSuccess] = useState(false);
  const [activeTag, setActiveTag] = useState<string | null>(null);

  async function handleQuickNote(e: FormEvent) {
    e.preventDefault();
    const title = quickNoteTitle.trim();
    if (!title) return;
    setQuickNoteSaving(true);
    setQuickNoteError("");
    try {
      const created = await api<PersonalNote>("/notes", {
        body: { title, body: "" },
      });
      addNote(created);
      setQuickNoteTitle("");
      setActiveTag(null);
      setQuickNoteSuccess(true);
      setTimeout(() => setQuickNoteSuccess(false), 3000);
    } catch (failure: unknown) {
      setQuickNoteError(errorMessage(failure));
    } finally {
      setQuickNoteSaving(false);
    }
  }

  function handleTagClick(prefix: string, tagLabel: string) {
    if (activeTag === tagLabel) {
      setActiveTag(null);
      if (quickNoteTitle.startsWith(prefix)) {
        setQuickNoteTitle(quickNoteTitle.slice(prefix.length));
      }
    } else {
      setActiveTag(tagLabel);
      let cleaned = quickNoteTitle;
      for (const t of NOTE_TAGS) {
        if (cleaned.startsWith(t.prefix)) {
          cleaned = cleaned.slice(t.prefix.length);
        }
      }
      setQuickNoteTitle(prefix + cleaned);
    }
    noteInputRef.current?.focus();
  }

  return (
    <section className="wb-card" aria-label="My Notes and quick jot">
      <div className="wb-card__header">
        <div>
          <h2 className="wb-card__title">
            <span className="wb-card__icon" aria-hidden="true">
              📝
            </span>
            <span>My Notes</span>
          </h2>
          <p className="wb-card__subtitle">Private reminders · Press N to jot quickly</p>
        </div>
        <Link to="/notes" className="wb-card__link">
          All notes →
        </Link>
      </div>

      <div className="wb-card__body">
        {/* Quick Tag Pills */}
        <div className="wb-tag-pills" role="region" aria-label="Note category tags">
          {NOTE_TAGS.map((tag) => {
            const isSelected = activeTag === tag.label;
            return (
              <button
                key={tag.label}
                type="button"
                className={`wb-tag-pill ${isSelected ? "wb-tag-pill--selected" : ""}`}
                onClick={() => handleTagClick(tag.prefix, tag.label)}
                title={`Add ${tag.label} prefix`}
              >
                <span aria-hidden="true">{tag.icon}</span> {tag.label}
              </button>
            );
          })}
        </div>

        {/* Quick Jot input form */}
        <form onSubmit={handleQuickNote} className="wb-quick-note-form">
          <label htmlFor="quick-note-input" className="wb-sr-only">
            Quick note or reminder
          </label>
          <div className="wb-quick-note-input-row">
            <input
              ref={noteInputRef}
              id="quick-note-input"
              type="text"
              className="wb-quick-note-input"
              placeholder="Jot a quick note or reminder... (Press Enter)"
              value={quickNoteTitle}
              onChange={(e) => setQuickNoteTitle(e.target.value)}
              maxLength={200}
              disabled={quickNoteSaving}
            />
            <button
              type="submit"
              className="wb-quick-note-btn"
              disabled={quickNoteSaving || !quickNoteTitle.trim()}
              aria-label="Add note"
            >
              {quickNoteSaving ? "..." : "+ Jot"}
            </button>
          </div>
          {quickNoteSuccess && (
            <p className="wb-quick-note-feedback" role="status">
              ✓ Saved to your private notes!
            </p>
          )}
        </form>

        {/* Recent notes list */}
        {(notesError || quickNoteError) && <p role="alert">{notesError || quickNoteError}</p>}
        {notesLoading ? (
          <Skeleton label="Loading notes" />
        ) : notes.length === 0 ? (
          <div className="wb-empty wb-empty--compact">
            <p className="wb-empty__text">No notes yet. Jot down an idea above!</p>
          </div>
        ) : (
          <ul className="wb-note-list">
            {notes.map((note) => (
              <li key={note.id} className="wb-note-item">
                <Link to="/notes" className="wb-note-item__link">
                  <strong className="wb-note-item__title">{note.title || "Untitled note"}</strong>
                  {note.body && <p className="wb-note-item__body">{note.body}</p>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
