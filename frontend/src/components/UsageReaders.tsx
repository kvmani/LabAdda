import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";

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
    load().catch((e) => setError(e.message));
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
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPassword("");
      setBusy(false);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    change(user);
  }
  return (
    <div className="card">
      <h2>Operational readers</h2>
      <p>
        Grant site storage metadata access only. This does not grant private content, policy editing or
        identity administration. Maximum duration: 30 days. Password confirmation is required for every
        change.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <form className="governance-form" onSubmit={submit}>
        <label>
          Operational reader account
          <select required value={user} onChange={(e) => setUser(e.target.value)}>
            <option value="">Choose an active non-administrator</option>
            {users
              .filter((u) => u.is_active && !u.is_admin)
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
          </select>
        </label>
        <label>
          Access duration (hours)
          <input
            type="number"
            required
            min={1}
            max={720}
            step={1}
            value={hours}
            onChange={(e) => setHours(Number(e.target.value))}
          />
        </label>
        <label>
          Access change reason
          <textarea
            required
            minLength={3}
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        <label>
          Confirm administrator password
          <input
            type="password"
            autoComplete="current-password"
            required
            maxLength={1024}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button disabled={busy}>Grant operational read access</button>
        <button type="button" disabled={busy || !user} onClick={() => change(user, true)}>
          Revoke selected account
        </button>
      </form>
      <table>
        <caption>
          Time-limited operational grants (active first, up to 200; use account selector for others)
        </caption>
        <thead>
          <tr>
            <th>Account</th>
            <th>Expiry</th>
            <th>State</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {grants.map((g) => (
            <tr key={g.user_id}>
              <td>{g.username}</td>
              <td>{new Date(g.expires_at).toLocaleString()}</td>
              <td>{g.active ? "Active" : "Expired or disabled"}</td>
              <td>
                <button disabled={busy} onClick={() => change(g.user_id, true)}>
                  Revoke {g.username}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>Enter a reason and confirm your password above before revoking a listed account.</p>
    </div>
  );
}
