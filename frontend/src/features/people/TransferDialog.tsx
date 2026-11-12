import { useState, type FormEvent } from "react";
import { Button, Checkbox, Dialog, EmptyState, ErrorState, Select, Skeleton, Stepper } from "../../ui";
import { PlanReview } from "./PlanReview";
import { openUnitOptions } from "./model";
import { useChangeReview } from "./useChangeReview";
import { usePeopleData } from "./usePeopleData";
import type { Role, TransferRequest } from "./changeTypes";
import type { AccessPage, StaffRecord, Unit } from "./types";

const STEPS = ["Unit and role", "Options", "Review", "Done"];
const ROLE_OPTIONS = [
  { value: "member", label: "Member" },
  { value: "steward", label: "Steward" },
];

type Draft = Omit<TransferRequest, "kind" | "person_id">;

function SharedSpaces({
  person,
  draft,
  onChange,
  onDenied,
}: {
  person: StaffRecord;
  draft: Draft;
  onChange: (draft: Draft) => void;
  onDenied: () => void;
}) {
  const access = usePeopleData<AccessPage>(
    `/admin/people/${encodeURIComponent(person.id)}/access?limit=100`,
    onDenied,
  );
  if (access.error) return <ErrorState message={access.error} onRetry={access.refresh} />;
  if (!access.data) return <Skeleton label="Loading projects and groups" />;
  const spaces = access.data.memberships.filter((item) => item.workspace.kind !== "org" && !item.inherited);
  function toggle(id: string, keep: boolean) {
    const leave = new Set(draft.leave_workspace_ids);
    if (keep) leave.delete(id);
    else leave.add(id);
    onChange({ ...draft, leave_workspace_ids: [...leave] });
  }
  return (
    <fieldset className="people-change__fieldset">
      <legend>Projects and groups to keep</legend>
      {!spaces.length && (
        <EmptyState title="No projects or groups">
          {person.display_name} is not in any project or group.
        </EmptyState>
      )}
      {spaces.map((item) => (
        <Checkbox
          key={item.workspace.id}
          label={`Keep ${item.workspace.name} (${item.workspace.kind === "project" ? "project" : "group"}, ${item.role})`}
          checked={!draft.leave_workspace_ids.includes(item.workspace.id)}
          onChange={(event) => toggle(item.workspace.id, event.target.checked)}
        />
      ))}
      {access.data.next_cursor && <p>Only the first 100 memberships are listed; the others are kept.</p>}
    </fieldset>
  );
}

/** Transfer: choose unit and role → options → review with before/after and a reason → done. */
export function TransferDialog({
  person,
  units,
  onClose,
  onDenied,
  onDone,
}: {
  person: StaffRecord;
  units: Unit[];
  onClose: () => void;
  onDenied: () => void;
  onDone: () => void;
}) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft>({
    to_unit_id: "",
    role: "member",
    keep_previous: false,
    leave_workspace_ids: [],
    acknowledge_no_steward: false,
  });
  const [reason, setReason] = useState("");
  const [missing, setMissing] = useState("");
  const review = useChangeReview(onDenied);
  const options = openUnitOptions(units, person.home_unit?.id);
  const request: TransferRequest = { kind: "transfer", person_id: person.id, ...draft };
  const busy = review.phase === "saving";
  const current = review.phase === "saved" ? 3 : step;
  const needsAcknowledgement = review.plan?.blockers.some((item) => item.code === "unit_without_steward");

  function next(event: FormEvent) {
    event.preventDefault();
    if (step === 0 && !draft.to_unit_id) return setMissing("Choose the new home unit.");
    setMissing("");
    if (step === 1) void review.preview(request);
    if (step === 2) {
      if (!review.plan) return void review.preview(request);
      if (reason.trim().length < 3) return setMissing("Give a reason of at least 3 characters.");
      return void review.confirm(request, reason.trim());
    }
    setStep(step + 1);
  }
  function back() {
    review.reset();
    setMissing("");
    setStep(step - 1);
  }
  function acknowledge(checked: boolean) {
    const changed = { ...draft, acknowledge_no_steward: checked };
    setDraft(changed);
    void review.preview({ ...request, ...changed });
  }
  function finish() {
    if (review.phase === "saved") onDone();
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
          form="transfer-form"
          busy={busy || review.phase === "checking"}
          busyLabel={busy ? "Transferring…" : "Checking…"}
          disabled={step === 2 && Boolean(review.plan?.blockers.length)}
        >
          {step === 2
            ? review.plan
              ? `Transfer ${person.display_name}`
              : "Check again"
            : step === 1
              ? "Review change"
              : "Next"}
        </Button>
      </>
    );
  const target = options.find((option) => option.value === draft.to_unit_id)?.label;
  return (
    <Dialog
      open
      title={`Transfer ${person.display_name}`}
      onClose={busy ? () => undefined : finish}
      size="lg"
      footer={footer}
    >
      <Stepper steps={STEPS} current={current} />
      {current === 3 ? (
        <div role="status" className="people-change">
          <p>
            {person.display_name} now has {target ?? "the new unit"} as their home unit.
          </p>
          <p>
            {review.receipt?.stewards_notified
              ? `${review.receipt.stewards_notified} steward notices were sent to reassign open tasks.`
              : "No steward notices were needed."}
          </p>
        </div>
      ) : (
        <form id="transfer-form" onSubmit={next} noValidate>
          {step === 0 &&
            (options.length ? (
              <div className="people-change__form">
                <p>Current home unit: {person.home_unit?.name ?? "None recorded"}</p>
                <Select
                  label="New home unit"
                  required
                  placeholder="Choose a unit"
                  options={options}
                  value={draft.to_unit_id}
                  onChange={(event) => setDraft({ ...draft, to_unit_id: event.target.value })}
                />
                <Select
                  label="Role in the new unit"
                  options={ROLE_OPTIONS}
                  value={draft.role}
                  onChange={(event) => setDraft({ ...draft, role: event.target.value as Role })}
                />
              </div>
            ) : (
              <EmptyState title="No other open units">Create another organisation unit first.</EmptyState>
            ))}
          {step === 1 && (
            <div className="people-change__form">
              <Checkbox
                label={`Keep access to ${person.home_unit?.name ?? "the current unit"} as additional access`}
                hint="Leave this unticked to remove the membership in the old unit."
                checked={draft.keep_previous}
                onChange={(event) => setDraft({ ...draft, keep_previous: event.target.checked })}
              />
              <SharedSpaces person={person} draft={draft} onChange={setDraft} onDenied={onDenied} />
            </div>
          )}
          {step === 2 && (
            <>
              <PlanReview
                plan={review.plan}
                checking={review.phase === "checking"}
                problem={review.problem}
                reason={reason}
                onReason={setReason}
              />
              {(needsAcknowledgement || draft.acknowledge_no_steward) && (
                <Checkbox
                  label="I understand the old unit will have no steward"
                  checked={draft.acknowledge_no_steward}
                  onChange={(event) => acknowledge(event.target.checked)}
                />
              )}
            </>
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
