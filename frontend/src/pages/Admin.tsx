import { useEffect, useState, type FormEvent } from "react";
import { UsageReaders } from "../components/UsageReaders";
import { Governance } from "../components/Governance";
import { api } from "../api";
import { kindLabel } from "../format";

type AdminUser = { id: string; username: string; display_name: string; is_active: boolean; is_admin: boolean; must_set_password: boolean };
type AdminWs = { id: string; name: string; kind: string; parent_id: string | null; archived: boolean; member_count: number };

export function Admin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [spaces, setSpaces] = useState<AdminWs[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [members, setMembers] = useState<any[]>([]);
  const [form, setForm] = useState({ username: "", display_name: "", is_admin: false });
  const [unit, setUnit] = useState({ name: "", kind: "org", parent_id: "" });
  const [grant, setGrant] = useState({ user_id: "", role: "member" });

  const load = async () => {
    try {
      const [u, w] = await Promise.all([api("/admin/users"), api("/admin/workspaces")]);
      setUsers(u.users);
      setSpaces(w.workspaces);
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (selected) api(`/admin/workspaces/${selected}/memberships`).then((r) => setMembers(r.memberships));
  }, [selected]);

  async function run(fn: () => Promise<any>) {
    setError(null);
    try {
      const r = await fn();
      await load();
      if (selected) setMembers((await api(`/admin/workspaces/${selected}/memberships`)).memberships);
      return r;
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function createUser(e: FormEvent) {
    e.preventDefault();
    const r = await run(() => api("/admin/users", { body: form }));
    if (r) {
      setToken(`Activation code for ${r.user.username}: ${r.activation_token} (expires ${new Date(r.expires_at).toLocaleString()}). Share it through an approved channel.`);
      setForm({ username: "", display_name: "", is_admin: false });
    }
  }

  const name = (id: string | null) => spaces.find((s) => s.id === id)?.name ?? "—";
  return (
    <section className="admin">
      <h1>Administration</h1>
      <p className="muted">Manage accounts, the organization tree and memberships. Administration does not grant access to workspace content or personal notes.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {token && <p className="notice" role="status">{token} <button className="ghost small" onClick={() => setToken(null)}>Hide</button></p>}
      <Governance />
      <UsageReaders users={users} />
      <div className="grid2">
        <div className="card">
          <h2>Accounts</h2>
          <form className="row wrap" onSubmit={createUser}>
            <input placeholder="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required aria-label="Username" />
            <input placeholder="Display name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required aria-label="Display name" />
            <label className="inline"><input type="checkbox" checked={form.is_admin} onChange={(e) => setForm({ ...form, is_admin: e.target.checked })} /> Admin</label>
            <button type="submit">Create</button>
          </form>
          <table>
            <thead><tr><th>User</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.display_name} <span className="muted small">@{u.username}</span></td>
                  <td>{u.is_active ? "Active" : "Disabled"}{u.is_admin ? " · Admin" : ""}{u.must_set_password ? " · Pending activation" : ""}</td>
                  <td className="row">
                    <button className="ghost small" onClick={() => run(() => api(`/admin/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }))}>{u.is_active ? "Disable" : "Enable"}</button>
                    <button className="ghost small" onClick={async () => { const r = await run(() => api(`/admin/users/${u.id}/reset`, { method: "POST" })); if (r) setToken(`Reset code for ${u.username}: ${r.reset_token}`); }}>Reset</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Workspaces</h2>
          <form className="row wrap" onSubmit={(e) => { e.preventDefault(); run(() => api("/admin/workspaces", { body: { name: unit.name, kind: unit.kind, parent_id: unit.kind === "org" ? unit.parent_id || null : null } })); }}>
            <input placeholder="Name" value={unit.name} onChange={(e) => setUnit({ ...unit, name: e.target.value })} required aria-label="Workspace name" />
            <select value={unit.kind} onChange={(e) => setUnit({ ...unit, kind: e.target.value })} aria-label="Kind"><option value="org">Unit</option><option value="project">Project</option></select>
            {unit.kind === "org" && (
              <select value={unit.parent_id} onChange={(e) => setUnit({ ...unit, parent_id: e.target.value })} aria-label="Parent unit">
                <option value="">(root)</option>
                {spaces.filter((s) => s.kind === "org").map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
            <button type="submit">Add</button>
          </form>
          <table>
            <thead><tr><th>Name</th><th>Kind</th><th>Parent</th><th>Members</th></tr></thead>
            <tbody>
              {spaces.map((s) => (
                <tr key={s.id} className={selected === s.id ? "selected" : ""}>
                  <td><button className="ghost" onClick={() => setSelected(s.id)}>{s.name}</button>{s.archived && <span className="tag">Archived</span>}</td>
                  <td>{kindLabel(s.kind)}</td>
                  <td>{s.kind === "org" ? name(s.parent_id) : "—"}</td>
                  <td>{s.member_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {selected && (
        <div className="card">
          <h2>Memberships · {name(selected)}</h2>
          <form className="row wrap" onSubmit={(e) => { e.preventDefault(); run(() => api(`/admin/workspaces/${selected}/memberships`, { method: "PUT", body: grant })); }}>
            <select value={grant.user_id} onChange={(e) => setGrant({ ...grant, user_id: e.target.value })} required aria-label="User">
              <option value="">Choose user…</option>
              {users.filter((u) => u.is_active).map((u) => <option key={u.id} value={u.id}>{u.display_name}</option>)}
            </select>
            <select value={grant.role} onChange={(e) => setGrant({ ...grant, role: e.target.value })} aria-label="Role"><option value="member">Member</option><option value="steward">Steward</option></select>
            <button type="submit">Grant</button>
            <button type="button" className="ghost" onClick={() => run(() => api(`/admin/workspaces/${selected}`, { method: "PATCH", body: { archived: !spaces.find((s) => s.id === selected)?.archived } }))}>Toggle archive</button>
          </form>
          <ul className="plain">
            {members.map((m) => (
              <li key={m.id}>{m.display_name} — {m.role}
                <button className="ghost small" onClick={() => run(() => api(`/admin/workspaces/${selected}/memberships/${m.id}`, { method: "DELETE" }))}>Remove</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
