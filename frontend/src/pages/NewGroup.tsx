import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useWorkspaces } from "../workspaces";
import type { User } from "../types";

export function ColleaguePicker({ selected, onChange, exclude = [] }: { selected: User[]; onChange: (u: User[]) => void; exclude?: string[] }) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<User[]>([]);
  useEffect(() => {
    const t = window.setTimeout(() => {
      api("/directory", { params: { q } }).then((r) => setFound(r.users)).catch(() => setFound([]));
    }, 200);
    return () => window.clearTimeout(t);
  }, [q]);
  const chosen = new Set(selected.map((u) => u.id));
  const options = found.filter((u) => !chosen.has(u.id) && !exclude.includes(u.id));
  return (
    <div className="picker">
      <label>Find colleagues<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or username" /></label>
      {selected.length > 0 && (
        <ul className="plain chips" aria-label="Chosen colleagues">
          {selected.map((u) => (
            <li key={u.id} className="chip">{u.display_name}
              <button type="button" className="ghost small" aria-label={`Remove ${u.display_name}`} onClick={() => onChange(selected.filter((x) => x.id !== u.id))}>×</button>
            </li>
          ))}
        </ul>
      )}
      <ul className="plain options">
        {options.slice(0, 8).map((u) => (
          <li key={u.id}><button type="button" className="ghost" onClick={() => onChange([...selected, u])}>+ {u.display_name} <span className="muted small">@{u.username}</span></button></li>
        ))}
        {options.length === 0 && <li className="muted small">No matching colleagues.</li>}
      </ul>
    </div>
  );
}

export function NewGroup() {
  const navigate = useNavigate();
  const { reload } = useWorkspaces();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [members, setMembers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ws = await api("/groups", { body: { name, description, member_ids: members.map((m) => m.id) } });
      await reload();
      navigate(`/w/${ws.id}/noticeboard`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card narrow" onSubmit={submit} aria-labelledby="new-group-title">
      <h1 id="new-group-title">New collaborative group</h1>
      <p className="muted">A group gives you and chosen colleagues — from any section, division or project — a shared noticeboard, whiteboard and chat. It sits outside the organization tree: only members can see it, and nothing in it is visible to parent units or administrators.</p>
      <label>Group name<input value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} placeholder="e.g. Microscopy Reading Club" /></label>
      <label>Purpose (optional)<textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} maxLength={2000} /></label>
      <ColleaguePicker selected={members} onChange={setMembers} />
      <p className="muted small">You will be the group's steward. You can add or remove members and hand over stewardship later.</p>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy}>{busy ? "Creating…" : `Create group${members.length ? ` with ${members.length} colleague${members.length > 1 ? "s" : ""}` : ""}`}</button>
    </form>
  );
}
