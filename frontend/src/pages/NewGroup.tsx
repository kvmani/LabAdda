import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, errorMessage, outcomeUnknown } from "../api";
import { useWorkspaces } from "../workspaces";
import type { User, Workspace } from "../types";
import { Button, Card, IconButton, PageHeader, Tag, TextArea, TextInput } from "../ui";
import "./groups.css";

export function ColleaguePicker({
  selected,
  onChange,
  exclude = [],
}: {
  selected: User[];
  onChange: (u: User[]) => void;
  exclude?: string[];
}) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<User[]>([]);
  useEffect(() => {
    const t = window.setTimeout(() => {
      api<{ users: User[] }>("/directory", { params: { q } })
        .then((r) => setFound(r.users))
        .catch(() => setFound([]));
    }, 200);
    return () => window.clearTimeout(t);
  }, [q]);
  const chosen = new Set(selected.map((u) => u.id));
  const options = found.filter((u) => !chosen.has(u.id) && !exclude.includes(u.id));
  return (
    <div className="picker">
      <TextInput
        label="Find colleagues"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Name or username"
      />
      {selected.length > 0 && (
        <ul className="picker__chosen" aria-label="Chosen colleagues">
          {selected.map((u) => (
            <li key={u.id}>
              <Tag tone="info">{u.display_name}</Tag>
              <IconButton
                icon="close"
                size="sm"
                label={`Remove ${u.display_name}`}
                onClick={() => onChange(selected.filter((x) => x.id !== u.id))}
              />
            </li>
          ))}
        </ul>
      )}
      <ul className="picker__options">
        {options.slice(0, 8).map((u) => (
          <li key={u.id}>
            <Button variant="quiet" onClick={() => onChange([...selected, u])}>
              + {u.display_name} <span className="picker__username">@{u.username}</span>
            </Button>
          </li>
        ))}
        {options.length === 0 && <li className="picker__empty">No matching colleagues.</li>}
      </ul>
    </div>
  );
}

export function NewGroup() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const conversation = params.get("conversation") === "1";
  const generation = useRef(0);
  useEffect(
    () => () => {
      ++generation.current;
    },
    [],
  );
  const [unknown, setUnknown] = useState(false);
  const { reload } = useWorkspaces();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [members, setMembers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || unknown) return;
    const token = ++generation.current;
    setBusy(true);
    setError(null);
    try {
      const ws = await api<Workspace>("/groups", {
        body: {
          name: name || `Conversation with ${members.map((m) => m.display_name).join(", ")}`.slice(0, 120),
          description,
          member_ids: members.map((m) => m.id),
        },
      });
      await reload();
      if (token === generation.current) navigate(`/w/${ws.id}/${conversation ? "chat" : "noticeboard"}`);
    } catch (err: unknown) {
      if (token === generation.current) {
        setError(errorMessage(err));
        if (outcomeUnknown(err)) {
          setUnknown(true);
          void reload();
        }
      }
    } finally {
      if (token === generation.current) setBusy(false);
    }
  }

  const title = conversation ? "Start a private conversation" : "New collaborative group";
  return (
    <div className="new-group">
      <PageHeader
        title={title}
        scope={
          conversation
            ? "Choose one colleague. This creates a private group with the two of you and opens its chat. Membership can later be managed explicitly in that group."
            : undefined
        }
      />
      <Card>
        <form className="new-group__form" onSubmit={submit} aria-label={title}>
          <fieldset disabled={busy || unknown} className="new-group__fields">
            <p className="new-group__muted">
              A group gives you and chosen colleagues — from any section, division or project — a shared
              noticeboard, whiteboard and chat. It sits outside the organization tree: only members can see
              it, and nothing in it is visible to parent units or administrators.
            </p>
            <TextInput
              label="Group name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required={!conversation}
              maxLength={120}
              placeholder="e.g. Microscopy Journal Club"
            />
            <TextArea
              label="Purpose (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              maxLength={2000}
            />
            <ColleaguePicker
              selected={members}
              onChange={(users) => setMembers(conversation ? users.slice(-1) : users)}
            />
            <p className="new-group__muted">
              You will be the group's steward. You can add or remove members and hand over stewardship later.
            </p>
          </fieldset>
          {unknown && (
            <p role="status">
              Creation may have succeeded. Check My groups before creating another; this form will not repeat
              an uncertain creation.
            </p>
          )}
          {error && (
            <p className="new-group__error" role="alert">
              {error}
            </p>
          )}
          <div>
            <Button
              variant="primary"
              type="submit"
              busy={busy}
              busyLabel="Creating…"
              disabled={unknown || (conversation && members.length !== 1)}
            >
              {`Create group${members.length ? ` with ${members.length} colleague${members.length > 1 ? "s" : ""}` : ""}`}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
