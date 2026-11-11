import { errorMessage } from "../api";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "../session";
import { INSTANCE } from "../config";

export function Login({ next }: { next: string }) {
  const { signIn, expired } = useSession();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(username, password);
      navigate(next && next !== "/login" ? next : "/", { replace: true });
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <form className="card" onSubmit={submit} aria-labelledby="signin-title">
        <h1 id="signin-title">LabAdda</h1>
        <p className="muted">
          Sign in to your research workspace{INSTANCE !== "pilot" ? ` · ${INSTANCE}` : ""}
        </p>
        {expired && <p className="notice">Your session ended. Sign in again to continue.</p>}
        <label>
          Username
          <input
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
        </label>
        <label>
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="muted small">
          First time here? Use the <Link to="/activate">activation link</Link> from your administrator.
        </p>
      </form>
    </main>
  );
}

export function Activate() {
  const { activate } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [token, setToken] = useState(params.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError("Passwords do not match.");
    try {
      await activate(token.trim(), password);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      setError(errorMessage(err));
    }
  }

  return (
    <main className="auth">
      <form className="card" onSubmit={submit}>
        <h1>Set your password</h1>
        <label>
          Activation code
          <input
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
            autoComplete="one-time-code"
          />
        </label>
        <label>
          New password (at least 10 characters)
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={10}
            autoComplete="new-password"
          />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            autoComplete="new-password"
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit">Activate account</button>
        <p className="muted small">
          <Link to="/">Back to sign in</Link>
        </p>
      </form>
    </main>
  );
}
