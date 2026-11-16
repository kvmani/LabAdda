import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { invalidate } from "../../generation";
import { useWorkspaces } from "../../workspaces";
import type { User, Workspace } from "../../types";
import { Button, Card, ConfirmDialog, TextInput } from "../../ui";

type Appointment = {
  id: string;
  user: User;
  source_id: string;
  destination_id: string;
  expires_at: string | null;
  revision: number;
};
type Appointments = {
  delegations: Appointment[];
  candidates: User[];
  destination_id: string | null;
  has_more: boolean;
};

export function RepresentativeDelegations({ ws }: { ws: Workspace }) {
  const [data, setData] = useState<Appointments | null>(null);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [person, setPerson] = useState("");
  const [reason, setReason] = useState("");
  const [expiry, setExpiry] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Appointment | "appoint" | null>(null);
  const generation = useRef(0);
  const { reload } = useWorkspaces();
  const load = useCallback(async () => {
    const token = ++generation.current;
    try {
      const result = await api<Appointments>(`/workspaces/${ws.id}/delegations`, {
        params: { search, offset },
      });
      if (token === generation.current) setData(result);
    } catch (e: unknown) {
      if (token === generation.current) setError(errorMessage(e));
    }
  }, [ws.id, search, offset]);
  useEffect(() => {
    void load();
    return () => invalidate(generation);
  }, [load]);

  async function apply() {
    if (!pending || busy) return;
    setBusy(true);
    setError("");
    try {
      if (pending === "appoint") {
        await api(`/workspaces/${ws.id}/delegations`, {
          body: { user_id: person, reason, expires_at: expiry ? new Date(expiry).toISOString() : null },
        });
      } else {
        await api(`/workspaces/${ws.id}/delegations/${pending.id}/revoke`, {
          body: { revision: pending.revision, reason },
        });
      }
      setPending(null);
      setReason("");
      await load();
      await reload();
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Unit representatives">
      <p>
        Representatives can contribute to the immediate parent unit's boards, posts and chat. They cannot
        moderate or manage members.
      </p>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading representatives…</p>}
      {data && (
        <>
          <TextInput
            label="Find a representative by name"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPerson("");
            }}
          />
          <ul>
            {data.delegations.map((grant) => (
              <li key={grant.id}>
                {grant.user.display_name} —{" "}
                {grant.source_id === ws.id
                  ? "represents this unit at its parent"
                  : "represents a child unit here"}
                {grant.expires_at && ` (until ${new Date(grant.expires_at).toLocaleString()})`}
                <Button
                  variant="quiet"
                  disabled={busy || reason.trim().length < 3}
                  onClick={() => setPending(grant)}
                >
                  Revoke representation
                </Button>
              </li>
            ))}
          </ul>
          {offset > 0 && (
            <Button onClick={() => setOffset((value) => Math.max(0, value - 100))}>
              Previous representatives
            </Button>
          )}
          {data.has_more && (
            <Button onClick={() => setOffset((value) => value + 100)}>More representatives</Button>
          )}
          {data.delegations.length === 0 && <p>No delegated representatives.</p>}
          <TextInput
            label="Reason for appointment or revocation"
            value={reason}
            maxLength={500}
            onChange={(e) => setReason(e.target.value)}
          />
          {data.destination_id && !ws.archived && (
            <>
              <label htmlFor="representative-user">Representative</label>
              <select id="representative-user" value={person} onChange={(e) => setPerson(e.target.value)}>
                <option value="">Choose a colleague</option>
                {data.candidates.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.display_name}
                  </option>
                ))}
              </select>
              <label>
                Expiry (optional, your local time)
                <input type="datetime-local" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
              </label>
              <Button
                disabled={busy || !person || reason.trim().length < 3}
                onClick={() => setPending("appoint")}
              >
                Appoint representative
              </Button>
            </>
          )}
        </>
      )}
      <ConfirmDialog
        open={pending !== null}
        title={pending === "appoint" ? "Appoint representative?" : "Revoke representation?"}
        consequences={[
          pending === "appoint"
            ? `${data?.candidates.find((u) => u.id === person)?.display_name} will represent ${ws.name} at its immediate parent.`
            : `${pending?.user.display_name ?? "This colleague"} will lose this delegated contribution permission.`,
          "Other memberships and stewardship remain unchanged.",
        ]}
        confirmLabel={pending === "appoint" ? "Appoint representative" : "Revoke representation"}
        onCancel={() => setPending(null)}
        onConfirm={apply}
      />
    </Card>
  );
}
