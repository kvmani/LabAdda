import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, setCsrf, setUnauthenticatedHandler, errorMessage } from "../api";
import { realtime } from "../realtime";
import type { Workspace } from "../types";
import { Banner, Button, Card, TextInput } from "../ui";
import { Board } from "./Board";
import "./panel.css";

type PanelSession = {
  user: { id: string; display_name: string };
  workspace: { id: string; name: string; can_write: boolean; archived: boolean };
  csrf_token: string;
  expires_at: string;
  idle_seconds: number;
  instance: string;
};

const WARN_SECONDS = 30;

/** Shared touch panel: one board, one person, short-lived. Never uses a desktop session. */
export function PanelApp() {
  const [session, setSession] = useState<PanelSession | null>(null);
  const [checking, setChecking] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);

  const accept = useCallback((s: PanelSession | null, why?: string) => {
    setCsrf(s?.csrf_token ?? null);
    setSession(s); // dropping the session unmounts the board, discarding its state and transient input
    if (s) realtime.start();
    else realtime.stop();
    if (why) setNotice(why);
  }, []);

  useEffect(() => {
    document.title = "LabAdda panel";
    setUnauthenticatedHandler(() => accept(null, "The panel session ended. Enter a new code to continue."));
    api<PanelSession>("/panel/session")
      .then((s) => accept(s))
      .catch(() => accept(null))
      .finally(() => setChecking(false));
  }, [accept]);

  if (checking) return <p className="panel-state">Starting panel…</p>;
  if (!session)
    return (
      <PairScreen
        notice={notice}
        onPaired={(s) => {
          setNotice(null);
          accept(s);
        }}
      />
    );
  return <PanelBoard session={session} onEnd={(why) => accept(null, why)} />;
}

function PairScreen({ notice, onPaired }: { notice: string | null; onPaired: (s: PanelSession) => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onPaired(await api<PanelSession>("/panel/claim", { body: { code } }));
    } catch (err: unknown) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="panel-pair">
      <Card>
        <form className="panel-pair__form" onSubmit={submit}>
          <h1 className="panel-pair__title">LabAdda touch panel</h1>
          {notice && <Banner>{notice}</Banner>}
          <p>
            On your computer, open a workspace whiteboard and choose <strong>📺 Open on touch panel</strong>.
            Then enter the code here.
          </p>
          <div className="panel-pair__code">
            <TextInput
              label="Panel code"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              autoComplete="off"
              autoCapitalize="characters"
              spellCheck={false}
              placeholder="XXXX-XXXX"
              required
            />
          </div>
          {error && (
            <p className="panel-pair__error" role="alert">
              {error}
            </p>
          )}
          <div className="panel-pair__submit">
            <Button variant="primary" type="submit" busy={busy} busyLabel="Opening…">
              Open board
            </Button>
          </div>
          <p className="panel-pair__hint">
            The panel shows only the chosen board. It locks after a few idle minutes and keeps nothing after
            it ends.
          </p>
        </form>
      </Card>
    </main>
  );
}

function PanelBoard({ session, onEnd }: { session: PanelSession; onEnd: (why: string) => void }) {
  const last = useRef(Date.now());
  const lastPing = useRef(0);
  const [remaining, setRemaining] = useState(session.idle_seconds);
  const ending = useRef(false);

  const end = useCallback(
    async (reason: "ended" | "idle_lock") => {
      if (ending.current) return;
      ending.current = true;
      try {
        await api("/panel/end", { body: { reason } });
      } catch {
        /* already ended server-side */
      }
      onEnd(
        reason === "idle_lock"
          ? "Panel locked after inactivity. Enter a new code to continue."
          : "Session ended. The board was cleared from this panel.",
      );
    },
    [onEnd],
  );

  const touched = useCallback(() => {
    last.current = Date.now();
    // Tell the server about interaction at most every 20 s so its idle lock matches ours.
    if (Date.now() - lastPing.current > 20000) {
      lastPing.current = Date.now();
      api("/panel/activity", { method: "POST" }).catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => {
      const left = Math.ceil(session.idle_seconds - (Date.now() - last.current) / 1000);
      setRemaining(left);
      if (left <= 0) void end("idle_lock");
      if (Date.now() >= new Date(session.expires_at).getTime()) void end("ended");
    }, 1000);
    return () => window.clearInterval(t);
  }, [session, end]);

  const ws: Workspace = {
    id: session.workspace.id,
    name: session.workspace.name,
    kind: "org",
    description: "",
    parent_id: null,
    archived: session.workspace.archived,
    posting_policy: "open",
    role: "member",
    inherited: false,
    can_write: session.workspace.can_write,
    can_moderate: false,
    unread_chat: 0,
  };

  return (
    <div className="panel-shell" onPointerDownCapture={touched}>
      <header className="panel-bar">
        <strong className="panel-title">{session.workspace.name}</strong>
        <span className="panel-bar__who">Drawing as {session.user.display_name}</span>
        {remaining <= WARN_SECONDS && (
          <span className="lock-warning" role="alert">
            Locking in {Math.max(0, remaining)} s. Touch the screen to stay.
          </span>
        )}
        <div className="panel-bar__end">
          <Button variant="danger" onClick={() => end("ended")}>
            End session
          </Button>
        </div>
      </header>
      <Board ws={ws} panel userId={session.user.id} onActivity={touched} />
    </div>
  );
}
