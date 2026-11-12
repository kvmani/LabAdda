import { Button, Card, EmptyState, ErrorState, Skeleton, Tag } from "../../ui";
import { usePeopleData } from "../people/usePeopleData";
import type { Directory } from "../people/types";
import { unitPath } from "./layout";
import type { OrgUnit } from "./types";
import type { DragPayload } from "./useDrag";

export type UnitAction = "create" | "rename" | "move" | "merge" | "split" | "close";

function names(list: { name: string }[]): string {
  return list.length ? list.map((item) => item.name).join(", ") : "None";
}

function People({
  unit,
  onDenied,
  onTransfer,
  onDragStart,
  refreshKey,
}: {
  unit: OrgUnit;
  onDenied: () => void;
  onTransfer: (id: string) => void;
  onDragStart: (event: React.PointerEvent, payload: DragPayload) => void;
  refreshKey: number;
}) {
  const url = `/admin/people?unit_id=${encodeURIComponent(unit.id)}&include_children=false&limit=100&r=${refreshKey}`;
  const result = usePeopleData<Directory>(url, onDenied);
  if (result.error) return <ErrorState message={result.error} onRetry={result.refresh} />;
  if (!result.data) return <Skeleton label="Loading people" />;
  if (!result.data.people.length)
    return <EmptyState title="No one yet">No one has {unit.name} as their home unit.</EmptyState>;
  return (
    <>
      <p className="org-panel__hint">Drag a name onto a unit in the chart, or use its Transfer button.</p>
      <ul className="org-panel__people">
        {result.data.people.map((person) => (
          <li key={person.id}>
            <span
              className="org-panel__person"
              onPointerDown={(event) =>
                onDragStart(event, { kind: "person", id: person.id, label: person.display_name })
              }
            >
              {person.display_name}
              {person.positions
                .filter((item) => item.workspace.id === unit.id)
                .map((item) => (
                  <Tag key={item.id} tone="info">
                    {item.acting ? "Acting " : ""}
                    {item.position === "head" ? "Head" : item.position === "deputy" ? "Deputy" : "Charge"}
                  </Tag>
                ))}
              {person.status !== "active" && <Tag>{person.status.replace("_", " ")}</Tag>}
            </span>
            <Button variant="quiet" onClick={() => onTransfer(person.id)}>
              {`Transfer ${person.display_name}`}
            </Button>
          </li>
        ))}
      </ul>
      {result.data.next_cursor && (
        <p>Only the first 100 people are listed. Use the People page for the rest.</p>
      )}
    </>
  );
}

/** Everything about one unit and every action on it; the same actions the drag gestures open. */
export function UnitPanel({
  unit,
  units,
  isRoot,
  refreshKey,
  onSelect,
  onAction,
  onTransfer,
  onDragStart,
  onDenied,
}: {
  unit: OrgUnit;
  units: OrgUnit[];
  isRoot: boolean;
  refreshKey: number;
  onSelect: (id: string) => void;
  onAction: (action: UnitAction) => void;
  onTransfer: (personId: string) => void;
  onDragStart: (event: React.PointerEvent, payload: DragPayload) => void;
  onDenied: () => void;
}) {
  const children = units.filter((item) => item.parent_id === unit.id);
  return (
    <Card title={unit.name} actions={unit.archived ? <Tag tone="warn">Closed</Tag> : undefined}>
      <dl className="org-panel__facts">
        <div>
          <dt>Code</dt>
          <dd>{unit.code ?? "None"}</dd>
        </div>
        <div>
          <dt>Under</dt>
          <dd>{unit.parent_id ? unitPath(units, unit.parent_id) : "Top of the organisation"}</dd>
        </div>
        <div>
          <dt>Head</dt>
          <dd>{unit.head?.name ?? "None appointed"}</dd>
        </div>
        {unit.acting_head && (
          <div>
            <dt>Acting head</dt>
            <dd>{unit.acting_head.name}</dd>
          </div>
        )}
        <div>
          <dt>Stewards</dt>
          <dd>{names(unit.stewards)}</dd>
        </div>
        <div>
          <dt>People</dt>
          <dd>
            {unit.people} with this home unit, {unit.members} with access
          </dd>
        </div>
      </dl>
      <div className="org-panel__actions" role="group" aria-label={`Actions for ${unit.name}`}>
        <Button icon="plus" onClick={() => onAction("create")} disabled={unit.archived}>
          Add sub-unit
        </Button>
        <Button onClick={() => onAction("rename")}>Rename or recode</Button>
        {!isRoot && <Button onClick={() => onAction("move")}>Move to…</Button>}
        {!isRoot && !unit.archived && <Button onClick={() => onAction("merge")}>Merge into…</Button>}
        {!isRoot && !unit.archived && (
          <Button onClick={() => onAction("split")}>Split off a new unit…</Button>
        )}
        {!isRoot && (
          <Button onClick={() => onAction("close")}>{unit.archived ? "Reopen unit" : "Close unit"}</Button>
        )}
      </div>
      <h3 className="org-panel__heading">Sub-units</h3>
      {children.length ? (
        <ul className="org-panel__subunits">
          {children.map((item) => (
            <li key={item.id}>
              <Button variant="quiet" onClick={() => onSelect(item.id)}>
                {item.name}
              </Button>
              {item.archived && <Tag tone="warn">Closed</Tag>}
            </li>
          ))}
        </ul>
      ) : (
        <p>No sub-units.</p>
      )}
      <h3 className="org-panel__heading">People</h3>
      <People
        unit={unit}
        onDenied={onDenied}
        onTransfer={onTransfer}
        onDragStart={onDragStart}
        refreshKey={refreshKey}
      />
    </Card>
  );
}
