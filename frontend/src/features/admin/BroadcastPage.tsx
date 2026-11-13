import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../../api";
import { BASE } from "../../config";
import { fmtTime } from "../../format";
import {
  Button,
  ConfirmDialog,
  DataTable,
  ErrorState,
  IconButton,
  PageHeader,
  Skeleton,
  Tag,
  type Column,
  type Tone,
} from "../../ui";
import { BroadcastDialog } from "../broadcast/BroadcastDialog";
import type { Broadcast, BroadcastList, BroadcastStatus } from "../broadcast/types";
import { useAdminData } from "./useAdminData";

const STATUS: Record<BroadcastStatus, { label: string; tone: Tone }> = {
  showing: { label: "Showing now", tone: "ok" },
  scheduled: { label: "Waiting for start time", tone: "info" },
  ended: { label: "Ended", tone: "neutral" },
  off: { label: "Turned off", tone: "neutral" },
};

function when(row: Broadcast): string {
  const from = row.starts_at ? `from ${fmtTime(row.starts_at)}` : "from now";
  return row.ends_at ? `${from} until ${fmtTime(row.ends_at)}` : `${from}, no end`;
}

/** Console Broadcast section: the messages scrolled across the top of every page (AD-11). */
export function BroadcastPage() {
  const { data, error, reload } = useAdminData<BroadcastList>("/admin/broadcasts");
  const [editing, setEditing] = useState<Broadcast | "new" | null>(null);
  const [removing, setRemoving] = useState<Broadcast | null>(null);
  const [problem, setProblem] = useState("");

  async function change(run: () => Promise<unknown>) {
    setProblem("");
    try {
      await run();
      reload();
    } catch (failure) {
      setProblem(errorMessage(failure));
    }
  }

  const rows = data?.broadcasts ?? [];
  const columns: Column<Broadcast>[] = [
    { key: "message", header: "Message", render: (row) => row.message },
    {
      key: "level",
      header: "Level",
      render: (row) => (
        <Tag tone={row.level === "warning" ? "warn" : "info"}>
          {row.level === "warning" ? "Warning" : "Information"}
        </Tag>
      ),
    },
    { key: "when", header: "Shown", render: when },
    {
      key: "status",
      header: "Status",
      render: (row) => <Tag tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Tag>,
    },
    {
      key: "order",
      header: "Order",
      render: (row) => (
        <span className="admin-form__row">
          <IconButton
            icon="arrow-up"
            size="sm"
            label={`Move message ${row.position} up`}
            disabled={row.position === rows[0]?.position}
            onClick={() =>
              void change(() =>
                api(`/admin/broadcasts/${row.id}/move`, { method: "POST", body: { direction: "up" } }),
              )
            }
          />
          <IconButton
            icon="arrow-down"
            size="sm"
            label={`Move message ${row.position} down`}
            disabled={row.position === rows[rows.length - 1]?.position}
            onClick={() =>
              void change(() =>
                api(`/admin/broadcasts/${row.id}/move`, { method: "POST", body: { direction: "down" } }),
              )
            }
          />
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      render: (row) => (
        <span className="admin-form__row">
          <Button size="sm" onClick={() => setEditing(row)}>
            Edit
          </Button>
          <Button
            size="sm"
            onClick={() =>
              void change(() =>
                api(`/admin/broadcasts/${row.id}`, {
                  method: "PATCH",
                  body: { active: !row.active, expected_revision: row.revision },
                }),
              )
            }
          >
            {row.active ? "Turn off" : "Turn on"}
          </Button>
          <Button size="sm" variant="danger" onClick={() => setRemoving(row)}>
            Delete
          </Button>
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Broadcast"
        scope="Messages that scroll across the top of every page for everyone who is signed in."
        helpHref={BASE + "/help/admin/broadcast"}
        action={
          <Button variant="primary" icon="plus" onClick={() => setEditing("new")}>
            Add broadcast message
          </Button>
        }
      />
      <p className="admin-note">
        Use this for news people must notice, such as planned maintenance.{" "}
        <Link to="/help/admin/broadcast">How broadcasts work</Link>
      </p>
      {problem && (
        <p role="alert" className="ui-field__error">
          {problem}
        </p>
      )}
      {error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data ? (
        <Skeleton label="Loading broadcasts" />
      ) : (
        <DataTable
          caption="Broadcast messages"
          columns={columns}
          rows={rows}
          rowKey={(row) => String(row.id)}
          empty={{
            title: "No broadcast messages",
            body: "Nothing is scrolling across the top of the pages.",
          }}
        />
      )}
      {editing && data && (
        <BroadcastDialog
          current={editing === "new" ? null : editing}
          maxLength={data.max_length}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
      <ConfirmDialog
        open={removing !== null}
        title="Delete this broadcast message?"
        danger
        consequences={[
          "The message stops showing for everyone at once.",
          "It cannot be brought back. Choose Turn off instead if you may want it again.",
          "The deletion is recorded in the audit trail, without the message text.",
        ]}
        confirmLabel="Delete broadcast message"
        onCancel={() => setRemoving(null)}
        onConfirm={async () => {
          if (!removing) return;
          await api(`/admin/broadcasts/${removing.id}`, { method: "DELETE" });
          setRemoving(null);
          reload();
        }}
      />
    </>
  );
}
