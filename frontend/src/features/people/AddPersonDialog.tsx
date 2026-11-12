import { useState, type FormEvent } from "react";
import { Button, DateInput, Dialog, EmptyState, Select, Stepper, TextInput } from "../../ui";
import { ActivationSlip } from "./ActivationSlip";
import { PlanReview } from "./PlanReview";
import { openUnitOptions } from "./model";
import { useChangeReview } from "./useChangeReview";
import type { AddPersonRequest, Role, StaffFieldsDraft } from "./changeTypes";
import type { Unit } from "./types";

const STEPS = ["Details", "Home unit and role", "Review", "Activation slip"];
const ROLE_OPTIONS = [
  { value: "member", label: "Member" },
  { value: "steward", label: "Steward" },
];
const EMPTY_FIELDS: StaffFieldsDraft = {
  designation: "",
  employee_no: "",
  contact_email: "",
  contact_phone: "",
};

type Draft = {
  display_name: string;
  username: string;
  fields: StaffFieldsDraft;
  joined_on: string;
  home_unit_id: string;
  role: Role;
};

function toRequest(draft: Draft): AddPersonRequest {
  const fields = Object.fromEntries(Object.entries(draft.fields).filter(([, value]) => value.trim()));
  return {
    kind: "add_person",
    username: draft.username,
    display_name: draft.display_name,
    fields,
    home_unit_id: draft.home_unit_id,
    role: draft.role,
    ...(draft.joined_on ? { joined_on: draft.joined_on } : {}),
  };
}

function DetailsStep({ draft, onChange }: { draft: Draft; onChange: (draft: Draft) => void }) {
  const field = (name: keyof StaffFieldsDraft, value: string) =>
    onChange({ ...draft, fields: { ...draft.fields, [name]: value } });
  return (
    <div className="people-change__form">
      <TextInput
        label="Full name"
        required
        maxLength={120}
        value={draft.display_name}
        onChange={(event) => onChange({ ...draft, display_name: event.target.value })}
      />
      <TextInput
        label="Username"
        required
        maxLength={63}
        hint="Lowercase letters, digits, dot, dash or underscore. It cannot be changed later."
        value={draft.username}
        onChange={(event) => onChange({ ...draft, username: event.target.value })}
      />
      <TextInput
        label="Employee number"
        maxLength={64}
        value={draft.fields.employee_no}
        onChange={(event) => field("employee_no", event.target.value)}
      />
      <TextInput
        label="Designation"
        maxLength={120}
        value={draft.fields.designation}
        onChange={(event) => field("designation", event.target.value)}
      />
      <TextInput
        label="Work email"
        type="email"
        maxLength={254}
        hint="Recorded only. LabAdda never sends email."
        value={draft.fields.contact_email}
        onChange={(event) => field("contact_email", event.target.value)}
      />
      <TextInput
        label="Phone extension"
        maxLength={64}
        value={draft.fields.contact_phone}
        onChange={(event) => field("contact_phone", event.target.value)}
      />
      <DateInput
        label="Start date"
        hint="Leave empty for today."
        value={draft.joined_on}
        onChange={(event) => onChange({ ...draft, joined_on: event.target.value })}
      />
    </div>
  );
}

/** Add a person: details → home unit and role → reviewed plan → one-time activation slip. */
export function AddPersonDialog({
  units,
  onClose,
  onDenied,
  onAdded,
}: {
  units: Unit[];
  onClose: () => void;
  onDenied: () => void;
  onAdded: (personId: string) => void;
}) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft>({
    display_name: "",
    username: "",
    fields: EMPTY_FIELDS,
    joined_on: "",
    home_unit_id: "",
    role: "member",
  });
  const [reason, setReason] = useState("");
  const [missing, setMissing] = useState("");
  const review = useChangeReview(onDenied);
  const options = openUnitOptions(units);
  const receipt = review.receipt;
  const busy = review.phase === "saving";

  function next(event: FormEvent) {
    event.preventDefault();
    if (step === 0 && (!draft.display_name.trim() || !draft.username.trim()))
      return setMissing("Enter the full name and a username.");
    if (step === 1 && !draft.home_unit_id) return setMissing("Choose the home unit.");
    setMissing("");
    if (step === 1) void review.preview(toRequest(draft));
    if (step === 2) {
      if (!review.plan) return void review.preview(toRequest(draft));
      if (reason.trim().length < 3) return setMissing("Give a reason of at least 3 characters.");
      return void review.confirm(toRequest(draft), reason.trim());
    }
    setStep(step + 1);
  }
  function back() {
    review.reset();
    setMissing("");
    setStep(step - 1);
  }
  const current = review.phase === "saved" ? 3 : step;
  function finish() {
    if (receipt?.person_id) onAdded(receipt.person_id);
    onClose();
  }
  const footer =
    current === 3 ? (
      <Button variant="primary" onClick={finish}>
        Done
      </Button>
    ) : (
      <>
        <Button onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        {step > 0 && (
          <Button onClick={back} disabled={busy}>
            Back
          </Button>
        )}
        <Button
          variant="primary"
          type="submit"
          form="add-person-form"
          busy={busy || review.phase === "checking"}
          busyLabel={busy ? "Adding…" : "Checking…"}
          disabled={step === 2 && Boolean(review.plan?.blockers.length)}
        >
          {step === 2 ? (review.plan ? "Add person" : "Check again") : step === 1 ? "Review change" : "Next"}
        </Button>
      </>
    );
  return (
    <Dialog
      open
      title="Add person"
      onClose={busy ? () => undefined : current === 3 ? finish : onClose}
      size="lg"
      footer={footer}
    >
      <Stepper steps={STEPS} current={current} />
      {current === 3 && receipt?.activation ? (
        <ActivationSlip
          displayName={draft.display_name.trim()}
          username={draft.username.trim().toLowerCase()}
          code={receipt.activation.code}
          expiresAt={receipt.activation.expires_at}
        />
      ) : (
        <form id="add-person-form" onSubmit={next} noValidate>
          {step === 0 && <DetailsStep draft={draft} onChange={setDraft} />}
          {step === 1 &&
            (options.length ? (
              <div className="people-change__form">
                <Select
                  label="Home unit"
                  required
                  placeholder="Choose a unit"
                  options={options}
                  value={draft.home_unit_id}
                  onChange={(event) => setDraft({ ...draft, home_unit_id: event.target.value })}
                />
                <Select
                  label="Role in the home unit"
                  options={ROLE_OPTIONS}
                  value={draft.role}
                  onChange={(event) => setDraft({ ...draft, role: event.target.value as Role })}
                />
              </div>
            ) : (
              <EmptyState title="No open units">Create an organisation unit before adding people.</EmptyState>
            ))}
          {step === 2 && (
            <PlanReview
              plan={review.plan}
              checking={review.phase === "checking"}
              problem={review.problem}
              reason={reason}
              onReason={setReason}
            />
          )}
          {missing && (
            <p className="people-change__problem" role="alert">
              {missing}
            </p>
          )}
        </form>
      )}
    </Dialog>
  );
}
