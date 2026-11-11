import { useState } from "react";
import { api, errorMessage } from "../../api";
import { fmtTime } from "../../format";
import { Button, EmptyState, ErrorState, Skeleton, Tag } from "../../ui";
import type { OwnSession } from "./types";

type Props = {
  sessions: OwnSession[] | null;
  error: string;
  timezone: string;
  onRetry: () => void;
};

/** Only the person's own live sessions; ending another one takes effect on its next request. */
export function SessionsList({ sessions, error, timezone, onRetry }: Props) {
  const [ending, setEnding] = useState<string | null>(null);
  const [failure, setFailure] = useState("");
  const [notice, setNotice] = useState("");
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (!sessions) return <Skeleton label="Loading your sessions" />;
  if (!sessions.length)
    return <EmptyState title="No active sessions">Sign in again to see this session here.</EmptyState>;

  async function end(session: OwnSession) {
    setEnding(session.id);
    setFailure("");
    setNotice("");
    try {
      await api(`/me/sessions/${encodeURIComponent(session.id)}`, { method: "DELETE" });
      setNotice(`Signed out ${session.browser}.`);
    } catch (e: unknown) {
      setFailure(errorMessage(e));
    } finally {
      setEnding(null);
      onRetry();
    }
  }

  return (
    <>
      {failure && (
        <p role="alert" className="ui-field__error">
          {failure}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <ul className="profile-list">
        {sessions.map((session) => (
          <li key={session.id}>
            <span>
              <strong>{session.browser}</strong> {session.current && <Tag tone="ok">This session</Tag>}
              <br />
              Signed in {fmtTime(session.started_at, timezone)} · Last active{" "}
              {fmtTime(session.last_seen_at, timezone)}
            </span>
            {!session.current && (
              <Button
                size="sm"
                busy={ending === session.id}
                busyLabel="Signing out…"
                aria-label={`Sign out this session (${session.browser})`}
                onClick={() => void end(session)}
              >
                Sign out this session
              </Button>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
