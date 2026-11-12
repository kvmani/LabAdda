import { useEffect, useRef, useState, type FormEvent } from "react";
import { invalidate } from "../generation";
import { api, errorMessage, errorStatus, outcomeUnknown } from "../api";
import { Link } from "react-router-dom";
import { Button, Card, Checkbox, ErrorState, PageHeader, Skeleton } from "../ui";
import "./preferences.css";
type Choices = { mentions: boolean; official_notices: boolean; reminders: boolean; revision: number };
/** Loads and saves alert choices; a lost or unconfirmed save forces a reload before the next try. */
function useAlertPreferences() {
  const [choices, setChoices] = useState<Choices | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [reloadNeeded, setReloadNeeded] = useState(false);
  const generation = useRef(0);

  async function load() {
    generation.current += 1;
    const token = generation.current;
    setBusy(true);
    setError("");
    try {
      const current = await api<Choices>("/notification-preferences");
      if (token === generation.current) {
        setChoices(current);
        setReloadNeeded(false);
        setMessage("Current alert choices loaded.");
      }
    } catch (e: unknown) {
      if (token === generation.current) setError(errorMessage(e));
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }

  useEffect(() => {
    void load();
    return () => {
      invalidate(generation);
    };
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || reloadNeeded || !choices) return;
    generation.current += 1;
    const token = generation.current;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api<Choices>("/notification-preferences", { method: "PUT", body: choices });
      if (token === generation.current) {
        setChoices(result);
        setMessage("Alert preferences saved.");
      }
    } catch (e: unknown) {
      if (token === generation.current) {
        setError(errorMessage(e));
        if (outcomeUnknown(e) || errorStatus(e) === 409) setReloadNeeded(true);
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }

  return { choices, setChoices, busy, error, message, reloadNeeded, load, save };
}

type Preferences = ReturnType<typeof useAlertPreferences>;

function CategoryForm({ preferences, choices }: { preferences: Preferences; choices: Choices }) {
  const { busy, reloadNeeded, setChoices } = preferences;
  return (
    <form onSubmit={preferences.save} aria-label="Alert preferences" className="preferences__form">
      <fieldset disabled={busy || reloadNeeded} className="preferences__fields">
        <legend className="ui-visually-hidden">My alert categories</legend>
        <Checkbox
          label="Mentions in posts and chat"
          checked={choices.mentions}
          onChange={(event) => setChoices({ ...choices, mentions: event.target.checked })}
        />
        <Checkbox
          label="Official notice alerts"
          checked={choices.official_notices}
          onChange={(event) => setChoices({ ...choices, official_notices: event.target.checked })}
        />
        <Checkbox
          label="Scheduled note and post reminders"
          checked={choices.reminders}
          onChange={(event) => setChoices({ ...choices, reminders: event.target.checked })}
        />
      </fieldset>
      {reloadNeeded && (
        <p>
          Your draft is kept. The result is unconfirmed or settings changed. Reload current preferences before
          saving; this replaces the draft.
        </p>
      )}
      <div>
        <Button variant="primary" type="submit" disabled={busy || reloadNeeded}>
          Save alert preferences
        </Button>
      </div>
    </form>
  );
}

export function AlertPreferences() {
  const preferences = useAlertPreferences();
  const { choices, busy, reloadNeeded } = preferences;
  return (
    <section className="preferences">
      <PageHeader
        title="Alert preferences"
        scope="Choose your in-app alerts. These choices apply to new alerts; existing alerts and shared content remain available. Enabling a category does not replay skipped reminders."
      />
      {preferences.error && (
        <ErrorState message={preferences.error} title="Alert preferences could not be updated" />
      )}
      {preferences.message && <p role="status">{preferences.message}</p>}
      {busy && !choices && <Skeleton lines={3} label="Loading alert preferences…" />}
      {choices && (
        <Card title="My alert categories" level={2}>
          <CategoryForm preferences={preferences} choices={choices} />
        </Card>
      )}
      <div>
        <Button icon="refresh" disabled={busy} onClick={preferences.load}>
          {reloadNeeded ? "Reload current preferences (replaces draft)" : "Refresh alert preferences"}
        </Button>
      </div>
      <p>
        These controls do not change who can read your content. Task due dates are shown in My day; they do
        not send automatic reminders in this stage.
      </p>
      <Link to="/today">Open My day</Link>
    </section>
  );
}
