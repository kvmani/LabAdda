import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useSession } from "../session";
import { useWorkspaces } from "../workspaces";
import type { User, Workspace } from "../types";
import { ColleaguePicker } from "./NewGroup";

type Member = User & { role: "member" | "steward" };

export function Members({ ws }: { ws: Workspace }) {
  const { session } = useSession();
  const { reload } = useWorkspaces();
  const navigate = useNavigate();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState<User[]>([]);
  const [confirmAdd, setConfirmAdd] = useState(false);
  const [name, setName] = useState(ws.name);
  const [description, setDescription] = useState(ws.description);
  const isGroup = ws.kind === "group";
  const manage = isGroup && ws.can_moderate;

  const load = useCallback(
    () =>
      api(`/workspaces/${ws.id}/members`)
        .then((r) => setMembers(r.members))
        .catch((e) => setError(e.message)),
    [ws.id],
  );
  useEffect(() => {
    load();
  }, [load]);

  async function run(fn: () => Promise<unknown>, after?: () => void) {
    setError(null);
    try {
      await fn();
      await load();
      await reload();
      after?.();
    } catch (e: any) {
      setError(e.message);
    }
  }

  const me = session!.user.id;
  return (
    <section className="members">
      <div className="card">
        <h2>{isGroup ? "Group members" : `Direct members of ${ws.name}`}</h2>
        {!isGroup && ws.kind === "org" && (
          <p className="muted small">
            Members of sub-units can also read and post here as inherited members.
          </p>
        )}
        {isGroup && (
          <p className="muted small">
            Only the people listed here can see this group. Parent units and administrators have no access.
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {!members ? (
          <p className="muted">Loading…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                {(manage || isGroup) && (
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id}>
                  <td>
                    {m.display_name} <span className="muted small">@{m.username}</span>
                    {!m.is_active && <span className="tag">Inactive</span>}
                  </td>
                  <td>{m.role === "steward" ? "Steward" : "Member"}</td>
                  {(manage || isGroup) && (
                    <td className="row">
                      {manage && !ws.archived && (
                        <button
                          className="ghost small"
                          onClick={() =>
                            run(() =>
                              api(`/groups/${ws.id}/members/${m.id}`, {
                                method: "PATCH",
                                body: { role: m.role === "steward" ? "member" : "steward" },
                              }),
                            )
                          }
                        >
                          {m.role === "steward" ? "Make member" : "Make steward"}
                        </button>
                      )}
                      {manage && m.id !== me && (
                        <button
                          className="ghost small"
                          onClick={() =>
                            window.confirm(`Remove ${m.display_name} from ${ws.name}?`) &&
                            run(() => api(`/groups/${ws.id}/members/${m.id}`, { method: "DELETE" }))
                          }
                        >
                          Remove
                        </button>
                      )}
                      {m.id === me && (
                        <button
                          className="ghost small"
                          onClick={() =>
                            window.confirm(`Leave ${ws.name}? You will lose access to its content.`) &&
                            run(
                              () => api(`/groups/${ws.id}/members/${me}`, { method: "DELETE" }),
                              () => navigate("/"),
                            )
                          }
                        >
                          Leave group
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {manage && !ws.archived && (
        <div className="card">
          <h2>Add colleagues</h2>
          <ColleaguePicker
            selected={adding}
            onChange={(u) => {
              setAdding(u);
              setConfirmAdd(false);
            }}
            exclude={members?.map((m) => m.id) ?? []}
          />
          {adding.length > 0 && (
            <label className="warning">
              <input type="checkbox" checked={confirmAdd} onChange={(e) => setConfirmAdd(e.target.checked)} />{" "}
              New members can read all existing posts, chat history and the board in{" "}
              <strong>{ws.name}</strong>.
            </label>
          )}
          <button
            disabled={!adding.length || !confirmAdd}
            onClick={() =>
              run(
                () => api(`/groups/${ws.id}/members`, { body: { user_ids: adding.map((u) => u.id) } }),
                () => setAdding([]),
              )
            }
          >
            Add {adding.length || ""} to group
          </button>
        </div>
      )}
      {manage && (
        <div className="card">
          <h2>Group settings</h2>
          <label>
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={ws.archived}
              maxLength={120}
            />
          </label>
          <label>
            Description
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={ws.archived}
              rows={2}
            />
          </label>
          <div className="row">
            {!ws.archived && (
              <button
                onClick={() =>
                  run(() => api(`/groups/${ws.id}`, { method: "PATCH", body: { name, description } }))
                }
              >
                Save
              </button>
            )}
            <button
              className="ghost"
              onClick={() =>
                window.confirm(
                  ws.archived
                    ? "Unarchive this group?"
                    : "Archive this group? Members keep read access but nobody can post.",
                ) && run(() => api(`/groups/${ws.id}`, { method: "PATCH", body: { archived: !ws.archived } }))
              }
            >
              {ws.archived ? "Unarchive group" : "Archive group"}
            </button>
            {!ws.archived && (
              <button
                className="ghost"
                onClick={() =>
                  run(() =>
                    api(`/workspaces/${ws.id}/policy`, {
                      method: "PATCH",
                      body: { posting_policy: ws.posting_policy === "open" ? "read_only" : "open" },
                    }),
                  )
                }
              >
                {ws.posting_policy === "open" ? "Make read-only for members" : "Reopen posting"}
              </button>
            )}
          </div>
        </div>
      )}
      {!isGroup && ws.can_moderate && !ws.archived && (
        <div className="card">
          <h2>Posting policy</h2>
          <p className="muted small">
            Currently {ws.posting_policy === "open" ? "open to all members" : "read-only for members"}.
          </p>
          <button
            onClick={() =>
              run(() =>
                api(`/workspaces/${ws.id}/policy`, {
                  method: "PATCH",
                  body: { posting_policy: ws.posting_policy === "open" ? "read_only" : "open" },
                }),
              )
            }
          >
            {ws.posting_policy === "open" ? "Make read-only for members" : "Reopen posting"}
          </button>
        </div>
      )}
    </section>
  );
}
