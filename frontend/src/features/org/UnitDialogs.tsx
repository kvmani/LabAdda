import { useState } from "react";
import { Checkbox, EmptyState, ErrorState, Select, Skeleton, TextInput, type SelectOption } from "../../ui";
import { ChangeDialog } from "../people/ChangeDialog";
import { SuccessorPicker } from "../people/SuccessorPicker";
import { usePeopleData } from "../people/usePeopleData";
import type { ChangeRequest } from "../people/changeTypes";
import type { Directory } from "../people/types";
import { descendantIds, unitPath } from "./layout";
import type { OrgUnit } from "./types";

export type UnitDialogProps = {
  unit: OrgUnit;
  units: OrgUnit[];
  onClose: () => void;
  onDenied: () => void;
  onDone: () => void;
};

const CODE_HINT = "2 to 24 capital letters, digits or dashes, for example SED-TF. Each code is used once.";

function openOptions(units: OrgUnit[], leave: Set<string>): SelectOption[] {
  return units
    .filter((item) => !item.archived && !leave.has(item.id))
    .map((item) => ({ value: item.id, label: unitPath(units, item.id) }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

function Plain({ text }: { text: string }) {
  return <p>{text}</p>;
}

/** Add a unit below the chosen one, optionally naming its Head. */
export function CreateUnitDialog({ unit, onClose, onDenied, onDone }: UnitDialogProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [head, setHead] = useState("");
  const request: ChangeRequest = {
    kind: "unit_create",
    parent_id: unit.id,
    name: name.trim(),
    code: code.trim().toUpperCase(),
    ...(head ? { head_id: head } : {}),
  };
  return (
    <ChangeDialog
      title={`New unit under ${unit.name}`}
      formId="unit-create"
      request={request}
      confirmLabel="Create unit"
      busyLabel="Creating…"
      missing={() => (name.trim() && code.trim() ? null : "Give the unit a name and a code.")}
      details={
        <div className="people-change__form">
          <TextInput
            label="Unit name"
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <TextInput
            label="Unit code"
            required
            hint={CODE_HINT}
            maxLength={24}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <SuccessorPicker
            workspaceId={unit.id}
            label="Head of the new unit (optional)"
            value={head}
            onChange={setHead}
            onDenied={onDenied}
          />
        </div>
      }
      done={() => <Plain text={`${name.trim()} now exists under ${unit.name}.`} />}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Change the name and/or the code; links and records keep working because the unit stays the same. */
export function RenameUnitDialog({ unit, onClose, onDenied, onDone }: UnitDialogProps) {
  const [name, setName] = useState(unit.name);
  const [code, setCode] = useState(unit.code ?? "");
  const newName = name.trim();
  const newCode = code.trim().toUpperCase();
  const request: ChangeRequest = {
    kind: "unit_rename",
    unit_id: unit.id,
    ...(newName !== unit.name ? { name: newName } : {}),
    ...(newCode !== (unit.code ?? "") && newCode ? { code: newCode } : {}),
  };
  return (
    <ChangeDialog
      title={`Rename or recode ${unit.name}`}
      formId="unit-rename"
      request={request}
      confirmLabel="Save changes"
      busyLabel="Saving…"
      missing={() => (newName ? null : "A unit needs a name.")}
      details={
        <div className="people-change__form">
          <TextInput
            label="Unit name"
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <TextInput
            label="Unit code"
            hint={CODE_HINT}
            maxLength={24}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
      }
      done={() => <Plain text={`The unit is now called ${newName}.`} />}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Move a unit, with everything below it, under another open unit. */
export function MoveUnitDialog({
  unit,
  units,
  initialTarget = "",
  onClose,
  onDenied,
  onDone,
}: UnitDialogProps & { initialTarget?: string }) {
  const [target, setTarget] = useState(initialTarget);
  // Sub-units stay listed: choosing one is explained and blocked on the review, as a drop would be.
  const options = openOptions(units, new Set([unit.id, ...(unit.parent_id ? [unit.parent_id] : [])]));
  return (
    <ChangeDialog
      title={`Move ${unit.name}`}
      formId="unit-move"
      request={{ kind: "unit_move", unit_id: unit.id, new_parent_id: target }}
      confirmLabel={`Move ${unit.name}`}
      busyLabel="Moving…"
      missing={() => (target ? null : "Choose the unit to move it under.")}
      details={
        options.length ? (
          <div className="people-change__form">
            <p>
              {unit.name} is now under {unit.parent_id ? unitPath(units, unit.parent_id) : "nothing"}. Its
              sub-units move with it. The next step lists who gains or loses access to the units above.
            </p>
            <Select
              label="Move under"
              required
              placeholder="Choose a unit"
              options={options}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            />
          </div>
        ) : (
          <EmptyState title="Nowhere to move it">There is no other open unit it could go under.</EmptyState>
        )
      }
      done={() => <Plain text={`${unit.name} has been moved.`} />}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Merge this unit into another: its people move, and it stays readable as closed history. */
export function MergeUnitDialog({ unit, units, onClose, onDenied, onDone }: UnitDialogProps) {
  const [target, setTarget] = useState("");
  const options = openOptions(units, descendantIds(units, unit.id).add(unit.id));
  return (
    <ChangeDialog
      title={`Merge ${unit.name} into another unit`}
      formId="unit-merge"
      request={{ kind: "unit_merge", unit_id: unit.id, into_unit_id: target }}
      confirmLabel="Merge units"
      busyLabel="Merging…"
      missing={() => (target ? null : "Choose the unit to merge into.")}
      details={
        options.length ? (
          <div className="people-change__form">
            <p>
              People whose home is {unit.name} get the chosen unit as their home. {unit.name} is then closed.
              Nothing is deleted, and its members can still read its history.
            </p>
            <Select
              label="Merge into"
              required
              placeholder="Choose a unit"
              options={options}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
            />
          </div>
        ) : (
          <EmptyState title="Nothing to merge into">There is no other open unit.</EmptyState>
        )
      }
      done={() => <Plain text={`${unit.name} has been merged and closed.`} />}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

function PeopleToMove({
  unit,
  chosen,
  onChange,
  onDenied,
}: {
  unit: OrgUnit;
  chosen: string[];
  onChange: (ids: string[]) => void;
  onDenied: () => void;
}) {
  const url = `/admin/people?unit_id=${encodeURIComponent(unit.id)}&include_children=false&limit=100`;
  const result = usePeopleData<Directory>(url, onDenied);
  if (result.error) return <ErrorState message={result.error} onRetry={result.refresh} />;
  if (!result.data) return <Skeleton label="Loading people" />;
  const movable = result.data.people.filter((person) =>
    ["invited", "active", "on_leave"].includes(person.status),
  );
  if (!movable.length)
    return <EmptyState title="No one to move">No one has {unit.name} as their home unit.</EmptyState>;
  return (
    <fieldset className="people-change__fieldset">
      <legend>People who move to the new unit</legend>
      {movable.map((person) => (
        <Checkbox
          key={person.id}
          label={person.display_name}
          checked={chosen.includes(person.id)}
          onChange={(e) =>
            onChange(e.target.checked ? [...chosen, person.id] : chosen.filter((id) => id !== person.id))
          }
        />
      ))}
    </fieldset>
  );
}

/** Split a new sibling unit from this one and move the chosen people into it. */
export function SplitUnitDialog({ unit, onClose, onDenied, onDone }: UnitDialogProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [people, setPeople] = useState<string[]>([]);
  const [ack, setAck] = useState(false);
  const request: ChangeRequest = {
    kind: "unit_split",
    unit_id: unit.id,
    name: name.trim(),
    code: code.trim().toUpperCase(),
    person_ids: people,
    acknowledge_no_steward: ack,
  };
  return (
    <ChangeDialog
      title={`Split a new unit from ${unit.name}`}
      formId="unit-split"
      request={request}
      confirmLabel="Split unit"
      busyLabel="Splitting…"
      missing={() =>
        name.trim() && code.trim() && people.length
          ? null
          : "Give the new unit a name, a code and at least one person."
      }
      details={
        <div className="people-change__form">
          <TextInput
            label="New unit name"
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <TextInput
            label="New unit code"
            required
            hint={CODE_HINT}
            maxLength={24}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <PeopleToMove unit={unit} chosen={people} onChange={setPeople} onDenied={onDenied} />
        </div>
      }
      reviewControls={(plan) =>
        (ack || plan?.blockers.some((item) => item.code === "unit_without_steward")) && (
          <Checkbox
            label="I understand a unit will be left with no steward"
            checked={ack}
            onChange={(e) => setAck(e.target.checked)}
          />
        )
      }
      done={() => <Plain text={`${name.trim()} now exists and its people have moved.`} />}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Close or reopen: the review lists everything that blocks a close in plain words. */
export function CloseUnitDialog({ unit, onClose, onDenied, onDone }: UnitDialogProps) {
  const reopening = unit.archived;
  return (
    <ChangeDialog
      title={reopening ? `Reopen ${unit.name}` : `Close ${unit.name}`}
      formId="unit-close"
      request={{ kind: reopening ? "unit_reopen" : "unit_close", unit_id: unit.id }}
      confirmLabel={reopening ? "Reopen unit" : "Close unit"}
      busyLabel={reopening ? "Reopening…" : "Closing…"}
      done={() => (
        <Plain
          text={
            reopening ? `${unit.name} is open again.` : `${unit.name} is closed. Its history stays readable.`
          }
        />
      )}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}
