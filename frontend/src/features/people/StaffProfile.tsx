import { useState } from "react";
import { Button, Drawer, EmptyState, ErrorState, Skeleton, Tabs } from "../../ui";
import { calendarDate } from "./model";
import { TransferDialog } from "./TransferDialog";
import { NewActivationCode } from "./NewActivationCode";
import { usePeopleData } from "./usePeopleData";
import type { AccessPage, StaffRecord, TimelinePage, Unit } from "./types";

function RecordFields({ person }: { person: StaffRecord }) {
  const fields = [
    ["Username", person.username],
    ["Employee number", person.employee_no],
    ["Designation", person.designation],
    ["Home unit", person.home_unit?.name],
    ["Employment status", person.status.replace(/_/g, " ")],
    ["Sign-in enabled", person.sign_in_enabled ? "Yes" : "No"],
    ["Site administrator", person.is_admin ? "Yes" : "No"],
    ["Work email", person.contact_email],
    ["Phone extension", person.contact_phone],
    ["Status effective date", calendarDate(person.status_effective_on)],
    ["Expected return date", calendarDate(person.expected_return_on)],
    ["Date joined", calendarDate(person.joined_on)],
    ["Last sign-in date", calendarDate(person.last_seen_on)],
  ];
  return (
    <dl className="people-record">
      {fields.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value || "Not recorded"}</dd>
        </div>
      ))}
    </dl>
  );
}
function Access({ identity, onDenied }: { identity: string; onDenied: () => void }) {
  const [cursor, setCursor] = useState<string | null>(null);
  const result = usePeopleData<AccessPage>(
    `/admin/people/${encodeURIComponent(identity)}/access${cursor ? "?cursor=" + cursor : ""}`,
    onDenied,
  );
  if (result.error) return <ErrorState message={result.error} onRetry={result.refresh} />;
  if (!result.data) return <Skeleton label="Loading recorded access" />;
  return (
    <>
      <p>
        Recorded memberships do not let administrators read private work. Inherited access flows from child
        units to their parents.
      </p>
      {!result.data.memberships.length && (
        <EmptyState title="No recorded memberships">
          A home-unit label or administrator role does not grant workspace access.
        </EmptyState>
      )}
      <ul className="people-history">
        {result.data.memberships.map((item) => (
          <li key={item.workspace.id}>
            <strong>{item.workspace.name}</strong> · {item.role}
            <br />
            <span>{item.inherited ? "Inherited from a child unit" : "Direct membership"}</span>
            {item.workspace.archived && " · Archived workspace"}
            {!item.sign_in_enabled && " · Sign-in blocked"}
          </li>
        ))}
      </ul>
      {cursor && <Button onClick={() => setCursor(null)}>First access page</Button>}
      {result.data.next_cursor && (
        <Button onClick={() => setCursor(result.data?.next_cursor ?? null)}>Next access page</Button>
      )}
    </>
  );
}
function Timeline({ identity, onDenied }: { identity: string; onDenied: () => void }) {
  const [before, setBefore] = useState<number | null>(null);
  const result = usePeopleData<TimelinePage>(
    `/admin/people/${encodeURIComponent(identity)}/timeline${before ? "?before=" + before : ""}`,
    onDenied,
  );
  if (result.error) return <ErrorState message={result.error} onRetry={result.refresh} />;
  if (!result.data) return <Skeleton label="Loading staff history" />;
  return (
    <>
      <p>Dates use the site calendar. Sign-in times and private work are not shown.</p>
      {!result.data.items.length && (
        <EmptyState title="No recorded history">Older changes may have no recorded explanation.</EmptyState>
      )}
      <ol className="people-history">
        {result.data.items.map((item) => (
          <li key={item.id}>
            <strong>{item.summary}</strong>
            <br />
            {calendarDate(item.occurred_on)} · {item.actor?.display_name ?? "System or server operator"}
            {item.reason && <p>{item.reason}</p>}
          </li>
        ))}
      </ol>
      {before && <Button onClick={() => setBefore(null)}>Newest staff history</Button>}
      {result.data.next_cursor && (
        <Button onClick={() => setBefore(result.data?.next_cursor ?? null)}>Older staff history</Button>
      )}
    </>
  );
}

/** Each staff selection mounts its own scope and cannot render another person's delayed response. */
export function StaffProfile({
  identity,
  view,
  onView,
  onClose,
  onDenied,
  units,
  onChanged,
}: {
  identity: string;
  view: string;
  onView: (view: string) => void;
  onClose: () => void;
  onDenied: () => void;
  units: Unit[] | null;
  onChanged: () => void;
}) {
  const record = usePeopleData<StaffRecord>(`/admin/people/${encodeURIComponent(identity)}`, onDenied);
  const [transferring, setTransferring] = useState(false);
  const person = record.data;
  const selected = ["record", "access", "timeline"].includes(view) ? view : "record";
  return (
    <Drawer open title={record.data?.display_name || "Staff profile"} onClose={onClose}>
      {record.error ? (
        <ErrorState message={record.error} onRetry={record.refresh} />
      ) : !record.data ? (
        <Skeleton label="Loading staff profile" />
      ) : (
        <Tabs
          label="Staff profile sections"
          selected={selected}
          onSelect={onView}
          tabs={[
            { id: "record", label: "Record" },
            { id: "access", label: "Access" },
            { id: "timeline", label: "Timeline" },
          ]}
        >
          {selected === "record" ? (
            <>
              <div className="people-actions">
                <Button icon="unit" onClick={() => setTransferring(true)} disabled={!units}>
                  Transfer to another unit
                </Button>
                {record.data.status === "invited" && (
                  <NewActivationCode person={record.data} onDenied={onDenied} onIssued={onChanged} />
                )}
              </div>
              <RecordFields person={record.data} />
              <p>Appointments and scheduled staff changes will appear here in a future update.</p>
            </>
          ) : selected === "access" ? (
            <Access key={identity} identity={identity} onDenied={onDenied} />
          ) : (
            <Timeline key={identity} identity={identity} onDenied={onDenied} />
          )}
        </Tabs>
      )}
      {transferring && person && units && (
        <TransferDialog
          person={person}
          units={units}
          onClose={() => setTransferring(false)}
          onDenied={onDenied}
          onDone={() => {
            record.refresh();
            onChanged();
          }}
        />
      )}
    </Drawer>
  );
}
