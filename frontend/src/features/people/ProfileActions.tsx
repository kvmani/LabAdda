import { useState } from "react";
import { Button } from "../../ui";
import { LeaveDialog, ReturnDialog } from "./AbsenceDialogs";
import { AdditionalChargeDialog, AppointDialog, PromoteDialog } from "./AuthorityDialogs";
import { ReinstateDialog, RetireDialog, SuspendDialog } from "./DepartureDialogs";
import { TransferDialog } from "./TransferDialog";
import { AppointUnitAdminDialog } from "./UnitAdminDialogs";
import type { StaffRecord, Unit } from "./types";

type Action =
  | "transfer"
  | "promote"
  | "appoint"
  | "charge"
  | "leave"
  | "return"
  | "retire"
  | "suspend"
  | "reinstate"
  | "unit_admin";
const LABELS: Record<Action, string> = {
  transfer: "Transfer to another unit",
  promote: "Promote or change role",
  appoint: "Appoint to a position",
  charge: "Give additional charge",
  leave: "Record long leave",
  return: "Record return from leave",
  retire: "Retire or leave",
  suspend: "Suspend access",
  reinstate: "Reinstate",
  unit_admin: "Make unit administrator",
};
const BY_STATUS: Record<StaffRecord["status"], Action[]> = {
  invited: ["transfer", "promote", "suspend", "retire"],
  active: ["transfer", "promote", "appoint", "charge", "leave", "retire", "suspend"],
  on_leave: ["return", "transfer", "promote", "charge", "retire", "suspend"],
  suspended: ["reinstate", "retire"],
  retired: ["reinstate"],
  left: ["reinstate"],
};

/** The reviewed changes that fit the person's employment status; each opens its own dialog. */
export function ProfileActions({
  person,
  units,
  canAppoint = false,
  onDenied,
  onDone,
}: {
  person: StaffRecord;
  units: Unit[] | null;
  /** Only site administrators appoint unit administrators (PO-24). */
  canAppoint?: boolean;
  onDenied: () => void;
  onDone: () => void;
}) {
  const [open, setOpen] = useState<Action | null>(null);
  const close = () => setOpen(null);
  const props = { person, onClose: close, onDenied, onDone };
  const needsUnits: Action[] = ["transfer", "appoint", "charge", "unit_admin"];
  const offered = [...BY_STATUS[person.status]];
  if (canAppoint && person.status === "active" && !person.is_admin) offered.push("unit_admin");
  return (
    <>
      <div className="people-actions" role="group" aria-label={`Changes for ${person.display_name}`}>
        {offered.map((action) => (
          <Button
            key={action}
            onClick={() => setOpen(action)}
            disabled={needsUnits.includes(action) && !units}
          >
            {LABELS[action]}
          </Button>
        ))}
      </div>
      {open === "transfer" && units && <TransferDialog {...props} units={units} />}
      {open === "promote" && <PromoteDialog {...props} />}
      {open === "appoint" && units && <AppointDialog {...props} units={units} />}
      {open === "charge" && units && <AdditionalChargeDialog {...props} units={units} />}
      {open === "leave" && <LeaveDialog {...props} />}
      {open === "return" && <ReturnDialog {...props} />}
      {open === "retire" && <RetireDialog {...props} />}
      {open === "suspend" && <SuspendDialog {...props} />}
      {open === "unit_admin" && units && <AppointUnitAdminDialog {...props} units={units} />}
      {open === "reinstate" && <ReinstateDialog {...props} />}
    </>
  );
}
