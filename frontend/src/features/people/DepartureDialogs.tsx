import { useState } from "react";
import { Checkbox, DateInput, ErrorState, Select, Skeleton } from "../../ui";
import { ActivationSlip } from "./ActivationSlip";
import type { PersonDialogProps } from "./AuthorityDialogs";
import { ChangeDialog } from "./ChangeDialog";
import { SuccessorPicker } from "./SuccessorPicker";
import { usePeopleData } from "./usePeopleData";
import type { ChangePlan, RetireRequest, SuccessorChoice } from "./changeTypes";
import type { AccessPage } from "./types";

const STATUS_OPTIONS = [
  { value: "retired", label: "Retired" },
  { value: "left", label: "Left the organisation" },
];
// Plan problems that a successor (or the acknowledgement) settles, keyed to their workspace.
const NEEDS_SUCCESSOR = new Set(["position_needs_successor", "group_needs_steward", "successor_not_member"]);
const NEEDS_ACKNOWLEDGEMENT = new Set(["position_needs_successor", "unit_without_steward"]);

function SuccessorChoices({
  plan,
  person,
  request,
  onChange,
  onDenied,
}: {
  plan: ChangePlan | null;
  person: PersonDialogProps["person"];
  request: RetireRequest;
  onChange: (request: RetireRequest) => void;
  onDenied: () => void;
}) {
  const chosen = new Map(request.successors.map((item) => [item.workspace_id, item]));
  const needed = (plan?.blockers ?? [])
    .filter((item) => NEEDS_SUCCESSOR.has(item.code) && item.target_id)
    .map((item) => item.target_id ?? "");
  const workspaces = [...new Set([...chosen.keys(), ...needed])];
  const positioned = new Set(
    person.positions.filter((item) => item.position !== "charge").map((item) => item.workspace.id),
  );
  const acknowledgeable = (plan?.blockers ?? []).some((item) => NEEDS_ACKNOWLEDGEMENT.has(item.code));
  function update(workspace: string, choice: Partial<SuccessorChoice> | null) {
    const others = request.successors.filter((item) => item.workspace_id !== workspace);
    const previous = chosen.get(workspace) ?? { workspace_id: workspace, successor_id: "" };
    const next = choice === null ? null : { ...previous, ...choice };
    const successors = next?.successor_id ? [...others, next] : others;
    onChange({ ...request, successors });
  }
  if (!workspaces.length && !acknowledgeable && !request.acknowledge_no_steward) return null;
  return (
    <fieldset className="people-change__fieldset">
      <legend>Who takes over</legend>
      {workspaces.map((workspace) => {
        const item = chosen.get(workspace);
        return (
          <div key={workspace} className="people-change__form">
            <SuccessorPicker
              workspaceId={workspace}
              label={positioned.has(workspace) ? "Successor in" : "New steward of"}
              named
              exclude={person.id}
              value={item?.successor_id ?? ""}
              onChange={(id) => update(workspace, id ? { successor_id: id } : null)}
              onDenied={onDenied}
            />
            {item && positioned.has(workspace) && (
              <Checkbox
                label="Acting appointment"
                hint="Ends by itself on the date below; a permanent choice is needed then."
                checked={Boolean(item.acting)}
                onChange={(event) =>
                  update(
                    workspace,
                    event.target.checked
                      ? { acting: true, ends_on: "" }
                      : { acting: false, ends_on: undefined },
                  )
                }
              />
            )}
            {item?.acting && (
              <DateInput
                label="Acting until"
                required
                value={item.ends_on ?? ""}
                onChange={(event) => update(workspace, { ends_on: event.target.value })}
              />
            )}
          </div>
        );
      })}
      {(acknowledgeable || request.acknowledge_no_steward) && (
        <Checkbox
          label="I understand a unit may be left without a Head or steward"
          checked={request.acknowledge_no_steward}
          onChange={(event) => onChange({ ...request, acknowledge_no_steward: event.target.checked })}
        />
      )}
    </fieldset>
  );
}

/** Acting successors need a date before the server can plan them; keep the last complete request. */
function plannable(request: RetireRequest): RetireRequest {
  return {
    ...request,
    successors: request.successors
      .filter((item) => !item.acting || item.ends_on)
      .map((item) =>
        item.acting ? item : { workspace_id: item.workspace_id, successor_id: item.successor_id },
      ),
  };
}

/** Retire or leave: positions end with successors, memberships go, sign-in and sessions end. */
export function RetireDialog({ person, onClose, onDenied, onDone }: PersonDialogProps) {
  const access = usePeopleData<AccessPage>(
    `/admin/people/${encodeURIComponent(person.id)}/access?limit=100`,
    onDenied,
  );
  const [request, setRequest] = useState<RetireRequest>({
    kind: "retire",
    person_id: person.id,
    status: "retired",
    keep_workspace_ids: [],
    successors: [],
    acknowledge_no_steward: false,
  });
  const direct = access.data?.memberships.filter((item) => !item.inherited) ?? [];
  function keep(id: string, kept: boolean) {
    const others = request.keep_workspace_ids.filter((item) => item !== id);
    setRequest({ ...request, keep_workspace_ids: kept ? [...others, id] : others });
  }
  const details = (
    <div className="people-change__form">
      <Select
        label="Reason for leaving"
        options={STATUS_OPTIONS}
        value={request.status}
        onChange={(event) =>
          setRequest({ ...request, status: event.target.value as RetireRequest["status"] })
        }
      />
      <p>The change takes effect today. Sign-in and every open session end at once.</p>
      {access.error ? (
        <ErrorState message={access.error} onRetry={access.refresh} />
      ) : !access.data ? (
        <Skeleton label="Loading memberships" />
      ) : (
        <fieldset className="people-change__fieldset">
          <legend>Memberships to keep on record</legend>
          {direct.map((item) => (
            <Checkbox
              key={item.workspace.id}
              label={`Keep ${item.workspace.name} (${item.role})`}
              hint="Kept memberships give no access while the account is closed."
              checked={request.keep_workspace_ids.includes(item.workspace.id)}
              onChange={(event) => keep(item.workspace.id, event.target.checked)}
            />
          ))}
        </fieldset>
      )}
    </div>
  );
  return (
    <ChangeDialog
      title={`Retire or leave: ${person.display_name}`}
      formId="retire-form"
      request={plannable(request)}
      details={details}
      reviewControls={(plan) => (
        <SuccessorChoices
          plan={plan}
          person={person}
          request={request}
          onChange={setRequest}
          onDenied={onDenied}
        />
      )}
      confirmLabel={`Close the account of ${person.display_name}`}
      busyLabel="Saving…"
      done={(receipt) => (
        <>
          <p>{person.display_name} can no longer sign in.</p>
          <p>
            {receipt?.stewards_notified
              ? `${receipt.stewards_notified} steward notices were sent to reassign open tasks.`
              : "No steward notices were needed."}
          </p>
        </>
      )}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Suspend: access stops at once; memberships stay on record but give no access. */
export function SuspendDialog({ person, onClose, onDenied, onDone }: PersonDialogProps) {
  return (
    <ChangeDialog
      title={`Suspend ${person.display_name}`}
      formId="suspend-form"
      request={{ kind: "suspend", person_id: person.id }}
      confirmLabel={`Suspend ${person.display_name}`}
      busyLabel="Suspending…"
      done={() => <p>{person.display_name} is suspended. Their open sessions have ended.</p>}
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}

/** Reinstate: invited again with a new one-time code; no earlier access comes back by itself. */
export function ReinstateDialog({ person, onClose, onDenied, onDone }: PersonDialogProps) {
  return (
    <ChangeDialog
      title={`Reinstate ${person.display_name}`}
      formId="reinstate-form"
      request={{ kind: "reinstate", person_id: person.id }}
      confirmLabel={`Reinstate ${person.display_name}`}
      busyLabel="Reinstating…"
      done={(receipt) =>
        receipt?.activation ? (
          <ActivationSlip
            displayName={person.display_name}
            username={person.username}
            code={receipt.activation.code}
            expiresAt={receipt.activation.expires_at}
          />
        ) : (
          <p>The account was reinstated, but the code was not received. Issue a password reset.</p>
        )
      }
      onClose={onClose}
      onDenied={onDenied}
      onDone={onDone}
    />
  );
}
