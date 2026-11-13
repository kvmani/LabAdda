import { useEffect, useState, type FormEvent } from "react";
import { fmtTime } from "../format";
import { api, errorMessage } from "../api";
import { Button, Card, DataTable, ErrorState, Select, TextArea, TextInput, type Column } from "../ui";
import "./storage.css";

type Candidate = { id: string; username: string; is_active: boolean; is_admin: boolean };
type Grant = { user_id: string; username: string; reason: string; expires_at: string; active: boolean };
export function UsageReaders({ users }: { users: Candidate[] }) {
  const [grants, setGrants] = useState<Grant[]>([]);
  const [user, setUser] = useState("");
  const [hours, setHours] = useState(24);
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setGrants((await api<{ grants: Grant[] }>("/admin/usage-readers")).grants);
  }
  useEffect(() => {
    load().catch((e) => setError(errorMessage(e)));
  }, []);
  async function change(target: string, revoke = false) {
    setError("");
    setMessage("");
    if (!password || reason.trim().length < 3) {
      setError("Enter your password and a meaningful reason.");
      return;
    }
    setBusy(true);
    try {
      await api(revoke ? "/admin/usage-readers/revoke" : "/admin/usage-readers", {
        body: { user_id: target, reason, password, ...(revoke ? {} : { hours }) },
      });
      await load();
      setMessage(revoke ? "Operational access revoked." : "Time-limited operational read access granted.");
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setPassword("");
      setBusy(false);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    void change(user);
  }
  const columns: Column<Grant>[] = [
    { key: "account", header: "Account", render: (g) => g.username },
    { key: "expiry", header: "Expiry", render: (g) => fmtTime(g.expires_at) },
    { key: "state", header: "State", render: (g) => (g.active ? "Active" : "Expired or disabled") },
    {
      key: "action",
      header: "Action",
      render: (g) => (
        <Button size="sm" disabled={busy} onClick={() => change(g.user_id, true)}>
          Revoke {g.username}
        </Button>
      ),
    },
  ];
  return (
    <Card title="Operational readers">
      <div className="storage-stack">
        <p>
          Grant site storage metadata access only. This does not grant private content, policy editing or
          identity administration. Maximum duration: 30 days. Password confirmation is required for every
          change.
        </p>
        {error && <ErrorState message={error} title="That change was not made" />}
        {message && <p role="status">{message}</p>}
        <form className="storage-form" onSubmit={submit}>
          <Select
            label="Operational reader account"
            required
            value={user}
            onChange={(e) => setUser(e.target.value)}
            placeholder="Choose an active non-administrator"
            options={users
              .filter((u) => u.is_active && !u.is_admin)
              .map((u) => ({ value: u.id, label: u.username }))}
          />
          <TextInput
            label="Access duration (hours)"
            type="number"
            required
            min={1}
            max={720}
            step={1}
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
          />
          <TextArea
            label="Access change reason"
            required
            minLength={3}
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <TextInput
            label="Confirm administrator password"
            type="password"
            autoComplete="current-password"
            required
            maxLength={1024}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div className="storage-actions">
            <Button variant="primary" type="submit" disabled={busy}>
              Grant operational read access
            </Button>
            <Button disabled={busy || !user} onClick={() => change(user, true)}>
              Revoke selected account
            </Button>
          </div>
        </form>
        <DataTable
          caption="Time-limited operational grants (active first, up to 200; use account selector for others)"
          columns={columns}
          rows={grants}
          rowKey={(g) => g.user_id}
        />
        <p>Enter a reason and confirm your password above before revoking a listed account.</p>
      </div>
    </Card>
  );
}
