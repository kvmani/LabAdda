import { useState } from "react";
import { Select } from "../../ui";
import { ChangeDialog } from "./ChangeDialog";
import { openUnitOptions } from "./model";
import type { PersonDialogProps } from "./AuthorityDialogs";
import type { UnitAdminRequest } from "./changeTypes";
import type { Unit } from "./types";

/** PO-24: appoint a person to administer one unit and the units below it. Site administrators only. */
export function AppointUnitAdminDialog({
  person,
  units,
  onClose,
  onDenied,
  onDone,
}: PersonDialogProps & { units: Unit[] }) {
  const [unit, setUnit] = useState("");
  const request: UnitAdminRequest = { kind: "unit_admin_grant", person_id: person.id, unit_id: unit };
  const details = (
    <div className="people-change__form">
      <Select
        label="Unit to administer"
        hint="They can manage people and units in this unit and below it. They never get access to its posts, chat, notes, files or board."
        required
        placeholder="Choose a unit"
        options={openUnitOptions(units)}
        value={unit}
        onChange={(event) => setUnit(event.target.value)}
      />
    </div>
  );
  return (
    <ChangeDialog
      title={`Make ${person.display_name} a unit administrator`}
      formId="unit-admin-form"
      request={request}
      details={details}
      missing={() => (unit ? null : "Choose the unit.")}
      confirmLabel="Appoint unit administrator"
      busyLabel="Saving…"
      done={() => <p>{person.display_name} can now manage people in that unit and below it.</p>}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Withdraw an appointment; takes effect on their next request. */
export function WithdrawUnitAdminDialog({
  person,
  unit,
  onClose,
  onDenied,
  onDone,
}: {
  person: { id: string; name: string };
  unit: { id: string; name: string };
  onClose: () => void;
  onDenied: () => void;
  onDone: () => void;
}) {
  const request: UnitAdminRequest = { kind: "unit_admin_revoke", person_id: person.id, unit_id: unit.id };
  return (
    <ChangeDialog
      title={`Withdraw ${person.name} as unit administrator of ${unit.name}`}
      formId="unit-admin-withdraw-form"
      request={request}
      confirmLabel="Withdraw appointment"
      busyLabel="Saving…"
      done={() => (
        <p>
          {person.name} no longer administers {unit.name}.
        </p>
      )}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}
