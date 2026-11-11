import { useCallback, useEffect, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { BASE } from "../../config";
import { fmtTime } from "../../format";
import { useSession } from "../../session";
import { Button, DataTable, ErrorState, PageHeader, Select, StatusPill, type Column } from "../../ui";
import type { ConsoleAccess } from "../admin/console";
import { usePolledData } from "../admin/usePolledData";
import { EventDetail } from "./EventDetail";
import {
  COMPONENT_OPTIONS,
  FILTER_KEYS,
  SEVERITY_OPTIONS,
  STATE_OPTIONS,
  eventsUrl,
  severityPill,
  stateLabel,
} from "./model";
import type { EventPage, OpsEvent } from "./types";
import "./events.css";

const POLL_MS = 30_000;

function columns(timezone: string, onOpen: (id: number) => void): Column<OpsEvent>[] {
  return [
    { key: "last", header: "Last seen", render: (event) => fmtTime(event.last_at, timezone) },
    {
      key: "severity",
      header: "Severity",
      render: (event) => <StatusPill {...severityPill[event.severity]} />,
    },
    {
      key: "what",
      header: "What happened",
      render: (event) => (
        <Button
          variant="quiet"
          size="sm"
          aria-label={`Open details: ${event.summary}`}
          onClick={() => onOpen(event.id)}
        >
          {event.summary}
        </Button>
      ),
    },
    { key: "where", header: "Where", render: (event) => event.component_label },
    { key: "count", header: "Times", align: "end", render: (event) => event.count },
    { key: "state", header: "Status", render: (event) => stateLabel(event.state) },
  ];
}

/** Operational events (AD-06): filters live in the URL; the list refreshes while the tab is visible. */
export function EventsPage() {
  const { session } = useSession();
  const { read_only } = useOutletContext<ConsoleAccess>();
  const [params, setParams] = useSearchParams();
  const [denied, setDenied] = useState(false);
  const [changed, setChanged] = useState<Record<number, OpsEvent>>({});
  const onDenied = useCallback(() => setDenied(true), []);
  const { data, error, loading, reload } = usePolledData<EventPage>(eventsUrl(params), POLL_MS, onDenied);
  // A just-saved event stays correct in the drawer until the next list answer replaces it.
  useEffect(() => setChanged({}), [data]);

  const change = (key: string, value: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== "cursor") next.delete("cursor");
      if (key !== "event") next.delete("event");
      return next;
    });
  const reset = () =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      for (const key of [...FILTER_KEYS, "cursor", "event"]) next.delete(key);
      return next;
    });
  const pick = (key: string) => ({
    value: params.get(key) ?? "",
    onChange: (event: { target: { value: string } }) => change(key, event.target.value),
  });

  const timezone = session?.timezone ?? "UTC";
  const header = (
    <PageHeader
      title="Events"
      scope="Problems the server noticed, newest first. Each links to what to do."
      helpHref={`${BASE}/help/admin/events`}
      action={
        <Button icon="refresh" onClick={reload}>
          Refresh
        </Button>
      }
    />
  );
  if (denied)
    return (
      <>
        {header}
        <ErrorState
          title="Your administration access changed"
          message="Events have been cleared. Reload to check access again."
          onRetry={() => window.location.reload()}
          retryLabel="Check administration access"
        />
      </>
    );
  const shown = data?.events.map((event) => changed[event.id] ?? event) ?? [];
  const open = shown.find((event) => String(event.id) === params.get("event"));
  return (
    <>
      {header}
      <section aria-label="Event filters" className="events-filters">
        <Select label="Status" placeholder="Any status" options={STATE_OPTIONS} {...pick("state")} />
        <Select
          label="Severity"
          placeholder="Any severity"
          options={SEVERITY_OPTIONS}
          {...pick("severity")}
        />
        <Select label="Where" placeholder="Anywhere" options={COMPONENT_OPTIONS} {...pick("component")} />
      </section>
      {error && !data ? (
        <ErrorState message={error} onRetry={reload} />
      ) : (
        <>
          {data && (
            <p role="status">
              Showing {data.events.length} {data.events.length === 1 ? "event" : "events"} on this page.
              {data.next_cursor ? " Older events are available." : " End of these results."}
            </p>
          )}
          <DataTable
            caption="Operational events, newest first"
            columns={columns(timezone, (id) => change("event", String(id)))}
            rows={shown}
            rowKey={(event) => String(event.id)}
            loading={loading}
            empty={{
              title: "No events match these filters",
              body: "Nothing needs attention here. Clear the filters to see every event.",
              action: <Button onClick={reset}>Clear event filters</Button>,
            }}
            footer={
              <div className="events-actions">
                {params.get("cursor") && <Button onClick={() => change("cursor", "")}>Newest events</Button>}
                {data?.next_cursor && (
                  <Button onClick={() => change("cursor", data.next_cursor ?? "")}>Older events</Button>
                )}
              </div>
            }
          />
        </>
      )}
      {open && (
        <EventDetail
          key={open.id}
          event={open}
          timezone={timezone}
          readOnly={read_only}
          onClose={() => change("event", "")}
          onChanged={(event) => {
            setChanged((previous) => ({ ...previous, [event.id]: event }));
            reload();
          }}
        />
      )}
    </>
  );
}
