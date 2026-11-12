import { Icon, Skeleton, Tag, TextArea } from "../../ui";
import type { ChangePlan, PlanIssue, PlanStep } from "./changeTypes";
import type { ReviewProblem } from "./useChangeReview";

const LABELS: Record<string, string> = {
  role: "Role",
  home: "Home unit",
  home_unit: "Home unit",
  activation: "Activation code",
  username: "Username",
  display_name: "Name",
  status: "Employment status",
  designation: "Designation",
  employee_no: "Employee number",
  contact_email: "Work email",
  contact_phone: "Phone extension",
  joined_on: "Date joined",
  expected_return_on: "Expected return date",
  sign_in: "Can sign in",
  position: "Position",
  unit: "Unit",
  ends_on: "Ends on",
  returns_to: "Role afterwards",
  is_admin: "Site administrator",
};
const HIDDEN = new Set(["home_unit_id"]);

function shown(value: unknown): string {
  if (value === null || value === undefined || value === "") return "None";
  if (value === true) return "Yes";
  if (value === false) return "No";
  if (typeof value === "string") return value.replace(/_/g, " ");
  if (typeof value === "number") return String(value);
  return "Recorded";
}

function StepChanges({ step }: { step: PlanStep }) {
  const keys = [...new Set([...Object.keys(step.before), ...Object.keys(step.after)])].filter(
    (key) => !HIDDEN.has(key),
  );
  if (!keys.length) return null;
  return (
    <dl className="people-change__values">
      {keys.map((key) => (
        <div key={key}>
          <dt>{LABELS[key] ?? key}</dt>
          <dd>
            {key in step.before && <span>Before: {shown(step.before[key])}</span>}
            <span>After: {shown(step.after[key])}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Issues({ items, blocking }: { items: PlanIssue[]; blocking: boolean }) {
  if (!items.length) return null;
  return (
    <section aria-label={blocking ? "Problems to fix first" : "Things to check"}>
      <h3 className="people-change__heading">{blocking ? "Problems to fix first" : "Things to check"}</h3>
      <ul className="people-change__issues">
        {items.map((item) => (
          <li key={`${item.code}:${item.target_id ?? ""}`}>
            <Icon name={blocking ? "error" : "warning"} />
            <Tag tone={blocking ? "danger" : "warn"}>{blocking ? "Blocked" : "Check"}</Tag>
            <span>{item.message}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The server's plan in plain sentences, with every before/after value, warning and blocker. */
export function PlanReview({
  plan,
  checking,
  problem,
  reason,
  onReason,
}: {
  plan: ChangePlan | null;
  checking: boolean;
  problem: ReviewProblem | null;
  reason: string;
  onReason: (value: string) => void;
}) {
  return (
    <div className="people-change">
      {problem && (
        <p className="people-change__problem" role="alert">
          <Icon name={problem.kind === "offline" ? "warning" : "error"} />
          <span>{problem.message}</span>
        </p>
      )}
      {checking && <Skeleton label="Checking what this change will do" />}
      {plan && (
        <>
          <h3 className="people-change__heading">What will happen</h3>
          <ol className="people-change__steps">
            {plan.steps.map((step, index) => (
              <li key={`${index}:${step.target_id}`}>
                <strong>{step.summary}</strong>
                <StepChanges step={step} />
              </li>
            ))}
          </ol>
          <p>
            {plan.affected_people === 1
              ? "1 person's access changes."
              : `${plan.affected_people} people's access changes.`}
          </p>
          <Issues items={plan.blockers} blocking />
          <Issues items={plan.warnings} blocking={false} />
          {!plan.blockers.length && (
            <TextArea
              label="Reason for this change"
              hint="Kept in the audit trail and shown on the person's timeline. At least 3 characters."
              value={reason}
              required
              maxLength={500}
              rows={3}
              onChange={(event) => onReason(event.target.value)}
            />
          )}
        </>
      )}
    </div>
  );
}
