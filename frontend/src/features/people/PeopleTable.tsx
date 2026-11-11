import { Button, DataTable, StatusPill, type Column } from "../../ui";
import { calendarDate, STATUS_OPTIONS } from "./model";
import type { Directory, Person } from "./types";

type Props = {
  data: Directory | null;
  loading: boolean;
  onOpen: (id: string) => void;
  onNext: (cursor: string) => void;
  onFirst: () => void;
  onReset: () => void;
  hasCursor: boolean;
};

/** Server sorting applies to all matching people, not just the visible page. */
function peopleColumns(onOpen: Props["onOpen"]): Column<Person>[] {
  return [
    {
      key: "name",
      header: "Name",
      render: (person) => (
        <Button
          variant="quiet"
          size="sm"
          aria-label={`View profile for ${person.display_name || person.username}`}
          onClick={() => onOpen(person.id)}
        >
          {person.display_name || person.username}
        </Button>
      ),
    },
    { key: "username", header: "Username", render: (person) => person.username },
    { key: "employee", header: "Employee number", render: (person) => person.employee_no ?? "Not recorded" },
    { key: "designation", header: "Designation", render: (person) => person.designation ?? "Not recorded" },
    { key: "unit", header: "Home unit", render: (person) => person.home_unit?.name ?? "Not recorded" },
    {
      key: "status",
      header: "Status",
      render: (person) => (
        <StatusPill
          tone="neutral"
          icon="user"
          label={STATUS_OPTIONS.find((item) => item.value === person.status)?.label ?? "Unknown"}
        />
      ),
    },
    { key: "seen", header: "Last sign-in date", render: (person) => calendarDate(person.last_seen_on) },
  ];
}

/** Keep paging server-owned and the current page usable by keyboard. */
export function PeopleTable({ data, loading, onOpen, onNext, onFirst, onReset, hasCursor }: Props) {
  return (
    <>
      {data && (
        <p role="status">
          Showing {data.people.length} {data.people.length === 1 ? "person" : "people"} on this page.
          {data.next_cursor ? " More people are available." : " End of these results."}
        </p>
      )}
      <DataTable
        caption="Staff directory"
        columns={peopleColumns(onOpen)}
        rows={data?.people ?? []}
        rowKey={(person) => person.id}
        loading={loading}
        empty={{
          title: "No people match these filters",
          body: "Clear the filters to see more people.",
          action: <Button onClick={onReset}>Clear people filters</Button>,
        }}
        footer={
          <div className="people-actions">
            {hasCursor && <Button onClick={onFirst}>First people page</Button>}
            {data?.next_cursor && (
              <Button onClick={() => onNext(data.next_cursor ?? "")}>Next people page</Button>
            )}
          </div>
        }
      />
    </>
  );
}
