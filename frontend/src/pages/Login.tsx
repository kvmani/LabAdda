import { Brand } from "../features/home/Brand";
import "../features/home/home.css";
import { errorMessage } from "../api";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useSession } from "../session";
import { INSTANCE } from "../config";
import { Button, Card, TextInput } from "../ui";
import "./auth.css";

export function Login({ next, embedded = false }: { next: string; embedded?: boolean }) {
  const Container = embedded ? "section" : "main";
  const { signIn, expired } = useSession();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return setError("Enter your username and password.");
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
    <Container className="auth">
      <Card>
        <form className="auth__form" onSubmit={submit} aria-labelledby="signin-title">
          <div>
            <h1 className="auth__title" id="signin-title">
              <Brand />
            </h1>
            <p className="auth__scope">
              Sign in to your research workspace{INSTANCE !== "pilot" ? ` · ${INSTANCE}` : ""}
            </p>
          </div>
          {expired && (
            <p className="auth__notice" role="status">
              Your session ended. Sign in again to continue.
            </p>
          )}
          <TextInput
            label="Username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            // The sign-in page has one purpose, so starting in the username field is expected.
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus={!embedded}
          />
          <TextInput
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={error}
          />
          <Button variant="primary" type="submit" busy={busy} busyLabel="Signing in…">
            Sign in
          </Button>
          <p className="auth__aside">
            First time here? Use the <Link to="/activate">activation link</Link> from your administrator.
          </p>
        </form>
      </Card>
    </Container>
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
    if (!token.trim() || !password) return setError("Enter the activation code and a new password.");
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
      <Card>
        <form className="auth__form" onSubmit={submit}>
          <h1 className="auth__title">Set your password</h1>
          <TextInput
            label="Activation code"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="one-time-code"
          />
          <TextInput
            label="New password (at least 10 characters)"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={10}
            autoComplete="new-password"
          />
          <TextInput
            label="Confirm password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            error={error}
          />
          <Button variant="primary" type="submit">
            Activate account
          </Button>
          <p className="auth__aside">
            <Link to="/">Back to sign in</Link>
          </p>
        </form>
      </Card>
    </main>
  );
}
