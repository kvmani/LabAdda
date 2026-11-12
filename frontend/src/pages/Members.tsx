import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useSession } from "../session";
import { useWorkspaces } from "../workspaces";
import type { User, Workspace } from "../types";
import { ColleaguePicker } from "./NewGroup";
import {
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  DataTable,
  Tag,
  TextArea,
  TextInput,
  type Column,
} from "../ui";
import "./groups.css";

type Member = User & { role: "member" | "steward" };
type Pending = {
  title: string;
  consequences: string[];
  confirmLabel: string;
  danger: boolean;
  act: () => Promise<void>;
};

export function Members({ ws }: { ws: Workspace }) {
  const { session } = useSession();
  const { reload } = useWorkspaces();
  const navigate = useNavigate();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState<User[]>([]);
  const [confirmAdd, setConfirmAdd] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [name, setName] = useState(ws.name);
  const [description, setDescription] = useState(ws.description);
  const isGroup = ws.kind === "group";
  const manage = isGroup && ws.can_moderate;

  const load = useCallback(
    () =>
      api<{ members: Member[] }>(`/workspaces/${ws.id}/members`)
        .then((r) => setMembers(r.members))
        .catch((e) => setError(errorMessage(e))),
    [ws.id],
  );
  useEffect(() => {
    void load();
  }, [load]);

  async function run(fn: () => Promise<unknown>, after?: () => void) {
    setError(null);
    try {
      await fn();
      await load();
      await reload();
      after?.();
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  }

  const finish = (after?: () => void) => async () => {
    await load();
    await reload();
    after?.();
  };
  const me = session!.user.id;
  const showActions = manage || isGroup;
  const postingPolicy = () =>
    run(() =>
      api(`/workspaces/${ws.id}/policy`, {
        method: "PATCH",
        body: { posting_policy: ws.posting_policy === "open" ? "read_only" : "open" },
      }),
    );
  const policyLabel = ws.posting_policy === "open" ? "Make read-only for members" : "Reopen posting";
  const confirm = (next: Pending) => setPending(next);
  const columns: Column<Member>[] = [
    {
      key: "name",
      header: "Name",
      render: (m) => (
        <>
          {m.display_name} <span className="members__muted">@{m.username}</span>
          {!m.is_active && <Tag>Inactive</Tag>}
        </>
      ),
    },
    { key: "role", header: "Role", render: (m) => (m.role === "steward" ? "Steward" : "Member") },
    ...(showActions
      ? [
          {
            key: "actions",
            header: "Actions",
            render: (m: Member) => (
              <div className="members__actions">
                {manage && !ws.archived && (
                  <Button
                    variant="quiet"
                    size="sm"
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
                  </Button>
                )}
                {manage && m.id !== me && (
                  <Button
                    variant="quiet"
                    size="sm"
                    onClick={() =>
                      confirm({
                        title: `Remove ${m.display_name}`,
                        consequences: [
                          `${m.display_name} loses access to everything in ${ws.name}, including past posts and chat.`,
                        ],
                        confirmLabel: `Remove ${m.display_name}`,
                        danger: true,
                        act: () =>
                          api(`/groups/${ws.id}/members/${m.id}`, { method: "DELETE" }).then(finish()),
                      })
                    }
                  >
                    Remove
                  </Button>
                )}
                {m.id === me && (
                  <Button
                    variant="quiet"
                    size="sm"
                    onClick={() =>
                      confirm({
                        title: `Leave ${ws.name}`,
                        consequences: ["You will lose access to its content."],
                        confirmLabel: "Leave group",
                        danger: true,
                        act: () =>
                          api(`/groups/${ws.id}/members/${me}`, { method: "DELETE" }).then(
                            finish(() => navigate("/")),
                          ),
                      })
                    }
                  >
                    Leave group
                  </Button>
                )}
              </div>
            ),
          },
        ]
      : []),
  ];
  return (
    <section className="members">
      <Card title={isGroup ? "Group members" : `Direct members of ${ws.name}`}>
        <div className="members__stack">
          {!isGroup && ws.kind === "org" && (
            <p className="members__muted">
              Members of sub-units can also read and post here as inherited members.
            </p>
          )}
          {isGroup && (
            <p className="members__muted">
              Only the people listed here can see this group. Parent units and administrators have no access.
            </p>
          )}
          {error && (
            <p className="members__error" role="alert">
              {error}
            </p>
          )}
          <DataTable
            caption={isGroup ? "Group members" : `Direct members of ${ws.name}`}
            columns={columns}
            rows={members ?? []}
            rowKey={(m) => m.id}
            loading={!members && !error}
            empty={{ title: "No members to show." }}
          />
        </div>
      </Card>
      {manage && !ws.archived && (
        <Card title="Add colleagues">
          <div className="members__stack">
            <ColleaguePicker
              selected={adding}
              onChange={(u) => {
                setAdding(u);
                setConfirmAdd(false);
              }}
              exclude={members?.map((m) => m.id) ?? []}
            />
            {adding.length > 0 && (
              <Checkbox
                label={`New members can read all existing posts, chat history and the board in ${ws.name}.`}
                checked={confirmAdd}
                onChange={(e) => setConfirmAdd(e.target.checked)}
              />
            )}
            <div>
              <Button
                variant="primary"
                disabled={!adding.length || !confirmAdd}
                onClick={() =>
                  run(
                    () => api(`/groups/${ws.id}/members`, { body: { user_ids: adding.map((u) => u.id) } }),
                    () => setAdding([]),
                  )
                }
              >
                Add {adding.length || ""} to group
              </Button>
            </div>
          </div>
        </Card>
      )}
      {manage && (
        <Card title="Group settings">
          <div className="members__stack">
            <TextInput
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={ws.archived}
              maxLength={120}
            />
            <TextArea
              label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={ws.archived}
              rows={2}
            />
            <div className="members__actions">
              {!ws.archived && (
                <Button
                  variant="primary"
                  onClick={() =>
                    run(() => api(`/groups/${ws.id}`, { method: "PATCH", body: { name, description } }))
                  }
                >
                  Save
                </Button>
              )}
              {!ws.archived && <Button onClick={postingPolicy}>{policyLabel}</Button>}
              <Button
                variant="danger"
                onClick={() =>
                  confirm({
                    title: ws.archived ? "Unarchive this group" : "Archive this group",
                    consequences: [
                      ws.archived
                        ? "Members can post again."
                        : "Members keep read access but nobody can post.",
                    ],
                    confirmLabel: ws.archived ? "Unarchive group" : "Archive group",
                    danger: !ws.archived,
                    act: () =>
                      api(`/groups/${ws.id}`, { method: "PATCH", body: { archived: !ws.archived } }).then(
                        finish(),
                      ),
                  })
                }
              >
                {ws.archived ? "Unarchive group" : "Archive group"}
              </Button>
            </div>
          </div>
        </Card>
      )}
      {!isGroup && ws.can_moderate && !ws.archived && (
        <Card title="Posting policy">
          <div className="members__stack">
            <p className="members__muted">
              Currently {ws.posting_policy === "open" ? "open to all members" : "read-only for members"}.
            </p>
            <div>
              <Button onClick={postingPolicy}>{policyLabel}</Button>
            </div>
          </div>
        </Card>
      )}
      <ConfirmDialog
        open={pending !== null}
        title={pending?.title ?? ""}
        consequences={pending?.consequences ?? []}
        confirmLabel={pending?.confirmLabel ?? ""}
        danger={pending?.danger}
        onConfirm={async () => {
          await pending?.act();
          setPending(null);
        }}
        onCancel={() => setPending(null)}
      />
    </section>
  );
}
