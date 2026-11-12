import { useState } from "react";
import { Checkbox, DateInput } from "../../ui";
import type { PersonDialogProps } from "./AuthorityDialogs";
import { ChangeDialog } from "./ChangeDialog";
import { positionLabel } from "./model";
import { SuccessorPicker } from "./SuccessorPicker";
import type { LeaveRequest } from "./changeTypes";

/** Long leave: expected return date, optional sign-in block, an acting replacement per position. */
export function LeaveDialog({ person, onClose, onDenied, onDone }: PersonDialogProps) {
  const [returnOn, setReturnOn] = useState("");
  const [block, setBlock] = useState(false);
  const [covers, setCovers] = useState<Record<string, string>>({});
  const held = person.positions.filter((item) => item.position !== "charge");
  const request: LeaveRequest = {
    kind: "leave",
    person_id: person.id,
    expected_return_on: returnOn,
    block_sign_in: block,
    acting: Object.entries(covers)
      .filter(([, successor]) => successor)
      .map(([position, successor]) => ({ position_id: position, successor_id: successor })),
  };
  const details = (
    <div className="people-change__form">
      <DateInput
        label="Expected return date"
        required
        value={returnOn}
        onChange={(event) => setReturnOn(event.target.value)}
      />
      <Checkbox
        label="Block sign-in while away"
        hint="Leave unticked to let them keep signing in. Ticking it ends their open sessions at once."
        checked={block}
        onChange={(event) => setBlock(event.target.checked)}
      />
      {held.map((item) => (
        <SuccessorPicker
          key={item.id}
          workspaceId={item.workspace.id}
          label={`Acting replacement for ${positionLabel(item)}`}
          exclude={person.id}
          value={covers[item.id] ?? ""}
          onChange={(id) => setCovers({ ...covers, [item.id]: id })}
          onDenied={onDenied}
        />
      ))}
    </div>
  );
  return (
    <ChangeDialog
      title={`Record long leave for ${person.display_name}`}
      formId="leave-form"
      request={request}
      details={details}
      missing={() => (returnOn ? null : "Choose the expected return date.")}
      confirmLabel="Record leave"
      busyLabel="Saving…"
      done={() => <p>{person.display_name} is now on leave. Acting appointments end on the return date.</p>}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Return from leave: active again; acting appointments made for the absence end. */
export function ReturnDialog({ person, onClose, onDenied, onDone }: PersonDialogProps) {
  return (
    <ChangeDialog
      title={`Record the return of ${person.display_name}`}
      formId="return-form"
      request={{ kind: "return", person_id: person.id }}
      confirmLabel="Record return"
      busyLabel="Saving…"
      done={() => <p>{person.display_name} is active again.</p>}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}
