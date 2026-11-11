import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api";
import { Link } from "react-router-dom";
type Choices = { mentions: boolean; official_notices: boolean; reminders: boolean; revision: number };
export function AlertPreferences() {
  const [choices, setChoices] = useState<Choices | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [reloadNeeded, setReloadNeeded] = useState(false);
  const generation = useRef(0);
  async function load() {
    const token = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const current = await api<Choices>("/notification-preferences");
      if (token === generation.current) {
        setChoices(current);
        setReloadNeeded(false);
        setMessage("Current alert choices loaded.");
      }
    } catch (e: any) {
      if (token === generation.current) setError(e.message);
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }
  useEffect(() => {
    load();
    return () => {
      ++generation.current;
    };
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || reloadNeeded || !choices) return;
    const token = ++generation.current;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<Choices>("/notification-preferences", { method: "PUT", body: choices });
      if (token === generation.current) {
        setChoices(result);
        setMessage("Alert preferences saved.");
      }
    } catch (e: any) {
      if (token === generation.current) {
        setError(e.message);
        if (e.status === 0 || e.status >= 500 || e.status === 409) setReloadNeeded(true);
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }
  return (
    <section className="card narrow">
      <h1>Alert preferences</h1>
      <p>
        Choose your in-app alerts. These choices apply to new alerts; existing alerts and shared content
        remain available. Enabling a category does not replay skipped reminders.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {busy && !choices && <p role="status">Loading alert preferences…</p>}
      {choices && (
        <form onSubmit={save} aria-label="Alert preferences">
          <fieldset disabled={busy || reloadNeeded}>
            <legend>My alert categories</legend>
            <label>
              <input
                type="checkbox"
                checked={choices.mentions}
                onChange={(event) => setChoices({ ...choices, mentions: event.target.checked })}
              />
              Mentions in posts and chat
            </label>
            <label>
              <input
                type="checkbox"
                checked={choices.official_notices}
                onChange={(event) => setChoices({ ...choices, official_notices: event.target.checked })}
              />
              Official notice alerts
            </label>
            <label>
              <input
                type="checkbox"
                checked={choices.reminders}
                onChange={(event) => setChoices({ ...choices, reminders: event.target.checked })}
              />
              Scheduled note and post reminders
            </label>
          </fieldset>
          {reloadNeeded && (
            <p>
              Your draft is kept. The result is unconfirmed or settings changed. Reload current preferences
              before saving; this replaces the draft.
            </p>
          )}
          <button type="submit" disabled={busy || reloadNeeded}>
            Save alert preferences
          </button>
        </form>
      )}
      <button type="button" disabled={busy} onClick={load}>
        {reloadNeeded ? "Reload current preferences (replaces draft)" : "Refresh alert preferences"}
      </button>
      <p>
        These controls do not change who can read your content. Task due dates are shown in My day; they do
        not send automatic reminders in this stage.
      </p>
      <Link to="/today">Open My day</Link>
    </section>
  );
}
