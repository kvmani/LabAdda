import { useState } from "react";
import { Checkbox, DateInput, ErrorState, Select, Skeleton, TextInput } from "../../ui";
import { ChangeDialog } from "./ChangeDialog";
import { openUnitOptions } from "./model";
import { usePeopleData } from "./usePeopleData";
import type {
  AdditionalChargeRequest,
  ChangeAuthorityRequest,
  PositionKind,
  PromoteRequest,
  Role,
} from "./changeTypes";
import type { AccessPage, StaffRecord, Unit } from "./types";

export type PersonDialogProps = {
  person: StaffRecord;
  onClose: () => void;
  onDenied: () => void;
  onDone: () => void;
};

export const ROLE_OPTIONS = [
  { value: "member", label: "Member" },
  { value: "steward", label: "Steward" },
];
const POSITION_OPTIONS = [
  { value: "head", label: "Head" },
  { value: "deputy", label: "Deputy" },
];

/** Promotion: a new designation and, optionally, a new role or vacant position in one of their units. */
export function PromoteDialog({ person, onClose, onDenied, onDone }: PersonDialogProps) {
  const access = usePeopleData<AccessPage>(
    `/admin/people/${encodeURIComponent(person.id)}/access?limit=100`,
    onDenied,
  );
  const [designation, setDesignation] = useState(person.designation ?? "");
  const [workspace, setWorkspace] = useState("");
  const [role, setRole] = useState<Role>("steward");
  const [position, setPosition] = useState<PositionKind | "">("");
  const changedDesignation = designation.trim() !== (person.designation ?? "");
  const request: PromoteRequest = {
    kind: "promote",
    person_id: person.id,
    ...(changedDesignation ? { designation: designation.trim() || null } : {}),
    ...(workspace ? { workspace_id: workspace, role } : {}),
    ...(workspace && position && role === "steward" ? { position } : {}),
  };
  const direct = access.data?.memberships.filter((item) => !item.inherited) ?? [];
  const details = (
    <div className="people-change__form">
      <TextInput
        label="Designation"
        hint="For example Scientific Officer E. Leave unchanged to keep it."
        maxLength={120}
        value={designation}
        onChange={(event) => setDesignation(event.target.value)}
      />
      {access.error ? (
        <ErrorState message={access.error} onRetry={access.refresh} />
      ) : !access.data ? (
        <Skeleton label="Loading memberships" />
      ) : (
        <Select
          label="Change the role in"
          placeholder="No role change"
          options={direct.map((item) => ({
            value: item.workspace.id,
            label: `${item.workspace.name} (now ${item.role})`,
          }))}
          value={workspace}
          onChange={(event) => setWorkspace(event.target.value)}
        />
      )}
      {workspace && (
        <>
          <Select
            label="New role"
            options={ROLE_OPTIONS}
            value={role}
            onChange={(event) => setRole(event.target.value as Role)}
          />
          {role === "steward" && (
            <Select
              label="Position in this unit"
              hint="Only a vacant position can be given here. To replace a Head, use Appoint to a position."
              placeholder="No position"
              options={POSITION_OPTIONS}
              value={position}
              onChange={(event) => setPosition(event.target.value as PositionKind | "")}
            />
          )}
        </>
      )}
    </div>
  );
  return (
    <ChangeDialog
      title={`Promote ${person.display_name}`}
      formId="promote-form"
      request={request}
      details={details}
      missing={() =>
        changedDesignation || workspace ? null : "Change the designation or choose a role to change."
      }
      confirmLabel={`Promote ${person.display_name}`}
      busyLabel="Saving…"
      done={() => <p>The promotion of {person.display_name} is recorded.</p>}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Appoint this person Head or Deputy of a unit, permanently or acting until a date (PO-14). */
export function AppointDialog({
  person,
  units,
  onClose,
  onDenied,
  onDone,
}: PersonDialogProps & { units: Unit[] }) {
  const [unit, setUnit] = useState("");
  const [position, setPosition] = useState<PositionKind>("head");
  const [acting, setActing] = useState(false);
  const [endsOn, setEndsOn] = useState("");
  const [outgoing, setOutgoing] = useState<Role>("steward");
  const request: ChangeAuthorityRequest = {
    kind: "change_authority",
    workspace_id: unit,
    position,
    successor_id: person.id,
    acting,
    ...(acting ? { ends_on: endsOn } : {}),
    outgoing_role: outgoing,
  };
  const details = (
    <div className="people-change__form">
      <Select
        label="Unit"
        required
        placeholder="Choose a unit"
        options={openUnitOptions(units)}
        value={unit}
        onChange={(event) => setUnit(event.target.value)}
      />
      <Select
        label="Position"
        options={POSITION_OPTIONS}
        value={position}
        onChange={(event) => setPosition(event.target.value as PositionKind)}
      />
      <Checkbox
        label="Acting appointment"
        hint="An acting appointment ends by itself on its end date and the role returns to what it was."
        checked={acting}
        onChange={(event) => setActing(event.target.checked)}
      />
      {acting && (
        <DateInput
          label="Acting until"
          required
          value={endsOn}
          onChange={(event) => setEndsOn(event.target.value)}
        />
      )}
      {position === "head" && (
        <Select
          label="The current Head stays as"
          hint="Their position ends. To move them or let them retire, use Transfer or Retire or leave."
          options={ROLE_OPTIONS}
          value={outgoing}
          onChange={(event) => setOutgoing(event.target.value as Role)}
        />
      )}
    </div>
  );
  return (
    <ChangeDialog
      title={`Appoint ${person.display_name} to a position`}
      formId="appoint-form"
      request={request}
      details={details}
      missing={() => (!unit ? "Choose the unit." : acting && !endsOn ? "Choose the end date." : null)}
      confirmLabel={`Appoint ${person.display_name}`}
      busyLabel="Appointing…"
      done={() => <p>{person.display_name} now holds the position. It shows on their profile.</p>}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Additional charge: access in a second unit, optionally a position, optionally until a date. */
export function AdditionalChargeDialog({
  person,
  units,
  onClose,
  onDenied,
  onDone,
}: PersonDialogProps & { units: Unit[] }) {
  const [unit, setUnit] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [position, setPosition] = useState<PositionKind | "">("");
  const [endsOn, setEndsOn] = useState("");
  const request: AdditionalChargeRequest = {
    kind: "additional_charge",
    person_id: person.id,
    workspace_id: unit,
    role: position ? "steward" : role,
    ...(position ? { position } : {}),
    ...(endsOn ? { ends_on: endsOn } : {}),
  };
  const details = (
    <div className="people-change__form">
      <Select
        label="Second unit"
        required
        placeholder="Choose a unit"
        options={openUnitOptions(units, person.home_unit?.id)}
        value={unit}
        onChange={(event) => setUnit(event.target.value)}
      />
      <Select
        label="Role in the second unit"
        options={ROLE_OPTIONS}
        value={position ? "steward" : role}
        disabled={Boolean(position)}
        onChange={(event) => setRole(event.target.value as Role)}
      />
      <Select
        label="Position in the second unit"
        placeholder="No position"
        options={POSITION_OPTIONS}
        value={position}
        onChange={(event) => setPosition(event.target.value as PositionKind | "")}
      />
      <DateInput
        label="Ends on"
        hint="Optional. On this date the access is removed automatically."
        value={endsOn}
        onChange={(event) => setEndsOn(event.target.value)}
      />
    </div>
  );
  return (
    <ChangeDialog
      title={`Give ${person.display_name} an additional charge`}
      formId="charge-form"
      request={request}
      details={details}
      missing={() => (unit ? null : "Choose the second unit.")}
      confirmLabel="Give additional charge"
      busyLabel="Saving…"
      done={() => <p>{person.display_name} now has access to the second unit.</p>}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}
