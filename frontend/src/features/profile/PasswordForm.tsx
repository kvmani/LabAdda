import { useState, type FormEvent } from "react";
import { api, errorCode, errorMessage, errorStatus } from "../../api";
import { Button, TextInput } from "../../ui";

type Props = { onChanged: () => void };

/** Current password is required; a failed attempt keeps what was typed so only the fault is fixed. */
export function PasswordForm({ onChanged }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<{ current?: string; next?: string; again?: string; form?: string }>(
    {},
  );
  const [saved, setSaved] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setSaved("");
    if (next !== again) {
      setErrors({ again: "The two new passwords do not match." });
      return;
    }
    setBusy(true);
    setErrors({});
    try {
      const result = await api<{ sessions_ended: number }>("/me/password", {
        body: { current_password: current, new_password: next },
      });
      setCurrent("");
      setNext("");
      setAgain("");
      const others = result.sessions_ended;
      setSaved(
        others === 0
          ? "Your password was changed. You were not signed in anywhere else."
          : `Your password was changed. ${others} other ${others === 1 ? "session was" : "sessions were"} signed out.`,
      );
      onChanged();
    } catch (error: unknown) {
      const code = errorCode(error);
      const message = errorMessage(error);
      if (code === "invalid_credentials") setErrors({ current: message });
      else if (code === "weak_password" || code === "password_unchanged") setErrors({ next: message });
      else if (errorStatus(error) === 429)
        setErrors({ form: "Too many attempts. Wait a few minutes, then try again." });
      else setErrors({ form: message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="profile-form" onSubmit={(event) => void submit(event)} aria-label="Change password">
      <TextInput
        label="Current password"
        type="password"
        autoComplete="current-password"
        required
        value={current}
        error={errors.current}
        onChange={(event) => setCurrent(event.target.value)}
      />
      <TextInput
        label="New password"
        type="password"
        autoComplete="new-password"
        required
        hint="At least 10 characters."
        value={next}
        error={errors.next}
        onChange={(event) => setNext(event.target.value)}
      />
      <TextInput
        label="Repeat new password"
        type="password"
        autoComplete="new-password"
        required
        value={again}
        error={errors.again}
        onChange={(event) => setAgain(event.target.value)}
      />
      {errors.form && (
        <p role="alert" className="ui-field__error">
          {errors.form}
        </p>
      )}
      {saved && <p role="status">{saved}</p>}
      <div>
        <Button
          type="submit"
          variant="primary"
          busy={busy}
          busyLabel="Changing password…"
          disabled={!current || !next || !again}
        >
          Change password
        </Button>
      </div>
    </form>
  );
}
