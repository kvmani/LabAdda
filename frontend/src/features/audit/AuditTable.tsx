import { Button, DataTable, StatusPill, type Column } from "../../ui";
import { fmtTime } from "../../format";
import { outcomeLabel } from "./model";
import type { AuditEvent, AuditPage } from "./types";

type Props = {
  data: AuditPage | null;
  loading: boolean;
  timezone: string;
  onOpen: (id: number) => void;
  onNext: (cursor: string) => void;
  onFirst: () => void;
  onReset: () => void;
  hasCursor: boolean;
};

function auditColumns(timezone: string, onOpen: Props["onOpen"]): Column<AuditEvent>[] {
  return [
    { key: "when", header: "When", render: (event) => fmtTime(event.created_at, timezone) },
    { key: "who", header: "Done by", render: (event) => event.actor?.display_name ?? "Operator tooling" },
    { key: "kind", header: "Kind", render: (event) => event.group_label },
    {
      key: "what",
      header: "What happened",
      render: (event) => (
        <Button
          variant="quiet"
          size="sm"
          aria-label={`Open details: ${event.sentence}`}
          onClick={() => onOpen(event.id)}
        >
          {event.sentence}
        </Button>
      ),
    },
    {
      key: "outcome",
      header: "Outcome",
      render: (event) => (
        <StatusPill
          tone={event.outcome === "success" ? "ok" : "warn"}
          icon={event.outcome === "success" ? "success" : "warning"}
          label={outcomeLabel(event.outcome)}
        />
      ),
    },
  ];
}

/** Newest first; the server owns order and paging so rows never shuffle under the reader. */
export function AuditTable({ data, loading, timezone, onOpen, onNext, onFirst, onReset, hasCursor }: Props) {
  return (
    <>
      {data && (
        <p role="status">
          Showing {data.events.length} {data.events.length === 1 ? "entry" : "entries"} on this page.
          {data.next_cursor ? " Older entries are available." : " End of these results."}
        </p>
      )}
      <DataTable
        caption="Audit trail, newest first"
        columns={auditColumns(timezone, onOpen)}
        rows={data?.events ?? []}
        rowKey={(event) => String(event.id)}
        loading={loading}
        empty={{
          title: "No audit entries match these filters",
          body: "Clear the filters to see more of the audit trail.",
          action: <Button onClick={onReset}>Clear audit filters</Button>,
        }}
        footer={
          <div className="audit-actions">
            {hasCursor && <Button onClick={onFirst}>Newest entries</Button>}
            {data?.next_cursor && (
              <Button onClick={() => onNext(data.next_cursor ?? "")}>Older entries</Button>
            )}
          </div>
        }
      />
    </>
  );
}
