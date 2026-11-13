import { useEffect, useState, type FormEvent } from "react";
import { fmtTime } from "../../format";
import type { WorkspaceMember } from "../../types";
import { api, errorMessage } from "../../api";
import { kindLabel } from "../../format";
import {
  Banner,
  Button,
  Card,
  Checkbox,
  DataTable,
  ErrorState,
  Select,
  Tag,
  TextInput,
  type Column,
} from "../../ui";
import "./basic.css";

type AdminUser = {
  id: string;
  username: string;
  display_name: string;
  is_active: boolean;
  is_admin: boolean;
  must_set_password: boolean;
};
type AdminWs = {
  id: string;
  name: string;
  kind: string;
  parent_id: string | null;
  archived: boolean;
  member_count: number;
};

export function BasicAdministration({ area }: { area: "people" | "org" }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [spaces, setSpaces] = useState<AdminWs[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [form, setForm] = useState({ username: "", display_name: "", is_admin: false });
  const [unit, setUnit] = useState({ name: "", kind: "org", parent_id: "" });
  const [grant, setGrant] = useState({ user_id: "", role: "member" });

  const load = async () => {
    try {
      const [u, w] = await Promise.all([
        api<{ users: AdminUser[] }>("/admin/users"),
        api<{ workspaces: AdminWs[] }>("/admin/workspaces"),
      ]);
      setUsers(u.users);
      setSpaces(w.workspaces);
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  };
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (selected)
      api<{ memberships: WorkspaceMember[] }>(`/admin/workspaces/${selected}/memberships`)
        .then((r) => setMembers(r.memberships))
        .catch((e) => setError(errorMessage(e)));
  }, [selected]);

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setError(null);
    try {
      const r = await fn();
      await load();
      if (selected)
        setMembers(
          (await api<{ memberships: WorkspaceMember[] }>(`/admin/workspaces/${selected}/memberships`))
            .memberships,
        );
      return r;
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  }

  async function createUser(e: FormEvent) {
    e.preventDefault();
    if (!form.username.trim() || !form.display_name.trim()) {
      setError("Enter a username and a display name.");
      return;
    }
    const r = await run(() =>
      api<{ user: AdminUser; activation_token: string; expires_at: string }>("/admin/users", { body: form }),
    );
    if (r) {
      setToken(
        `Activation code for ${r.user.username}: ${r.activation_token} (expires ${fmtTime(r.expires_at)}). Share it through an approved channel.`,
      );
      setForm({ username: "", display_name: "", is_admin: false });
    }
  }

  const name = (id: string | null) => spaces.find((s) => s.id === id)?.name ?? "—";
  const accountColumns: Column<AdminUser>[] = [
    {
      key: "user",
      header: "User",
      render: (u) => (
        <>
          {u.display_name} <span className="basic-admin__handle">@{u.username}</span>
        </>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (u) =>
        `${u.is_active ? "Active" : "Disabled"}${u.is_admin ? " · Admin" : ""}${
          u.must_set_password ? " · Pending activation" : ""
        }`,
    },
    {
      key: "actions",
      header: "Actions",
      render: (u) => (
        <span className="basic-admin__actions">
          <Button
            variant="quiet"
            size="sm"
            onClick={() =>
              run(() => api(`/admin/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }))
            }
          >
            {u.is_active ? "Disable" : "Enable"}
          </Button>
          <Button
            variant="quiet"
            size="sm"
            onClick={async () => {
              const r = await run(() =>
                api<{ reset_token: string; expires_at: string }>(`/admin/users/${u.id}/reset`, {
                  method: "POST",
                }),
              );
              if (r) setToken(`Reset code for ${u.username}: ${r.reset_token}`);
            }}
          >
            Reset
          </Button>
        </span>
      ),
    },
  ];
  const spaceColumns: Column<AdminWs>[] = [
    {
      key: "name",
      header: "Name",
      render: (s) => (
        <>
          <Button variant="quiet" size="sm" onClick={() => setSelected(s.id)}>
            {s.name}
          </Button>
          {s.archived && <Tag>Archived</Tag>}
        </>
      ),
    },
    { key: "kind", header: "Kind", render: (s) => kindLabel(s.kind) },
    { key: "parent", header: "Parent", render: (s) => (s.kind === "org" ? name(s.parent_id) : "—") },
    { key: "members", header: "Members", render: (s) => s.member_count },
  ];
  const parents = [
    { value: "", label: "(root)" },
    ...spaces.filter((s) => s.kind === "org").map((s) => ({ value: s.id, label: s.name })),
  ];
  return (
    <section className="basic-admin">
      {error && <ErrorState title="That did not work" message={error} />}
      {token && (
        <div className="basic-admin__notice">
          <Banner>{token}</Banner>
          <Button variant="quiet" size="sm" onClick={() => setToken(null)}>
            Hide
          </Button>
        </div>
      )}
      {area === "people" && (
        <Card title="Accounts">
          <form className="basic-admin__form" onSubmit={createUser}>
            <TextInput
              label="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
            <TextInput
              label="Display name"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            />
            <Checkbox
              label="Admin"
              checked={form.is_admin}
              onChange={(e) => setForm({ ...form, is_admin: e.target.checked })}
            />
            <Button variant="primary" type="submit">
              Create
            </Button>
          </form>
          <DataTable
            caption="Account administration table"
            columns={accountColumns}
            rows={users}
            rowKey={(u) => u.id}
            empty={{ title: "No accounts yet" }}
          />
        </Card>
      )}
      {area === "org" && (
        <Card title="Workspaces">
          <form
            className="basic-admin__form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!unit.name.trim()) {
                setError("Enter a workspace name.");
                return;
              }
              void run(() =>
                api("/admin/workspaces", {
                  body: {
                    name: unit.name,
                    kind: unit.kind,
                    parent_id: unit.kind === "org" ? unit.parent_id || null : null,
                  },
                }),
              );
            }}
          >
            <TextInput
              label="Workspace name"
              value={unit.name}
              onChange={(e) => setUnit({ ...unit, name: e.target.value })}
            />
            <Select
              label="Kind"
              value={unit.kind}
              onChange={(e) => setUnit({ ...unit, kind: e.target.value })}
              options={[
                { value: "org", label: "Unit" },
                { value: "project", label: "Project" },
              ]}
            />
            {unit.kind === "org" && (
              <Select
                label="Parent unit"
                value={unit.parent_id}
                onChange={(e) => setUnit({ ...unit, parent_id: e.target.value })}
                options={parents}
              />
            )}
            <Button variant="primary" type="submit">
              Add
            </Button>
          </form>
          <DataTable
            caption="Workspace administration table"
            columns={spaceColumns}
            rows={spaces}
            rowKey={(s) => s.id}
            empty={{ title: "No workspaces yet" }}
          />
        </Card>
      )}
      {area === "org" && selected && (
        <Card title={`Memberships · ${name(selected)}`}>
          <form
            className="basic-admin__form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!grant.user_id) {
                setError("Choose a user first.");
                return;
              }
              void run(() =>
                api(`/admin/workspaces/${selected}/memberships`, { method: "PUT", body: grant }),
              );
            }}
          >
            <Select
              label="User"
              value={grant.user_id}
              onChange={(e) => setGrant({ ...grant, user_id: e.target.value })}
              placeholder="Choose user…"
              options={users.filter((u) => u.is_active).map((u) => ({ value: u.id, label: u.display_name }))}
            />
            <Select
              label="Role"
              value={grant.role}
              onChange={(e) => setGrant({ ...grant, role: e.target.value })}
              options={[
                { value: "member", label: "Member" },
                { value: "steward", label: "Steward" },
              ]}
            />
            <Button variant="primary" type="submit">
              Grant
            </Button>
            <Button
              onClick={() =>
                run(() =>
                  api(`/admin/workspaces/${selected}`, {
                    method: "PATCH",
                    body: { archived: !spaces.find((s) => s.id === selected)?.archived },
                  }),
                )
              }
            >
              Toggle archive
            </Button>
          </form>
          <ul className="basic-admin__members">
            {members.map((m) => (
              <li key={m.id}>
                {m.display_name} — {m.role}
                <Button
                  variant="quiet"
                  size="sm"
                  onClick={() =>
                    run(() => api(`/admin/workspaces/${selected}/memberships/${m.id}`, { method: "DELETE" }))
                  }
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
}
