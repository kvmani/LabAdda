import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Button, Dialog, Stepper } from "../../ui";
import { PlanReview } from "./PlanReview";
import { useChangeReview } from "./useChangeReview";
import type { ChangePlan, ChangeReceipt, ChangeRequest } from "./changeTypes";

type Props = {
  title: string;
  formId: string;
  request: ChangeRequest;
  /** Fields chosen before the review; without them the dialog opens on the review. */
  details?: ReactNode;
  /** A plain message when a required detail is missing, or null. */
  missing?: () => string | null;
  /** Choices that refine the plan on the review step (successors, acknowledgements). */
  reviewControls?: (plan: ChangePlan | null) => ReactNode;
  confirmLabel: string;
  busyLabel: string;
  done: (receipt: ChangeReceipt | null) => ReactNode;
  onClose: () => void;
  onDenied: () => void;
  onDone: () => void;
};

/**
 * The shared shell of every reviewed staff change: details → review (the server's plan, its
 * warnings and blockers, and the required reason) → done. Any change to the request while the
 * review is open asks the server for a fresh plan, so what is applied is always what was shown.
 */
export function ChangeDialog({
  title,
  formId,
  request,
  details,
  missing,
  reviewControls,
  confirmLabel,
  busyLabel,
  done,
  onClose,
  onDenied,
  onDone,
}: Props) {
  const steps = details ? ["Details", "Review", "Done"] : ["Review", "Done"];
  const reviewIndex = details ? 1 : 0;
  const [step, setStep] = useState(0);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState("");
  const review = useChangeReview(onDenied);
  const busy = review.phase === "saving";
  const saved = review.phase === "saved";
  const current = saved ? steps.length - 1 : step;
  const reviewing = !saved && step === reviewIndex;
  const requestKey = JSON.stringify(request);

  useEffect(() => {
    if (reviewing) void review.preview(request);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-plan when the reviewed request changes
  }, [reviewing, requestKey]);

  function next(event: FormEvent) {
    event.preventDefault();
    const gap = missing?.() ?? null;
    if (gap) return setProblem(gap);
    setProblem("");
    if (!reviewing) return setStep(reviewIndex);
    if (!review.plan) return void review.preview(request);
    if (reason.trim().length < 3) return setProblem("Give a reason of at least 3 characters.");
    void review.confirm(request, reason.trim());
  }
  function back() {
    review.reset();
    setProblem("");
    setStep(0);
  }
  function finish() {
    if (saved) onDone();
    onClose();
  }
  const footer = saved ? (
    <Button variant="primary" onClick={finish}>
      Done
    </Button>
  ) : (
    <>
      <Button onClick={onClose} disabled={busy}>
        Cancel
      </Button>
      {reviewing && details && (
        <Button onClick={back} disabled={busy}>
          Back
        </Button>
      )}
      <Button
        variant="primary"
        type="submit"
        form={formId}
        busy={busy || review.phase === "checking"}
        busyLabel={busy ? busyLabel : "Checking…"}
        disabled={reviewing && Boolean(review.plan?.blockers.length)}
      >
        {reviewing ? (review.plan ? confirmLabel : "Check again") : "Review change"}
      </Button>
    </>
  );
  return (
    <Dialog open title={title} onClose={busy ? () => undefined : finish} size="lg" footer={footer}>
      <Stepper steps={steps} current={current} />
      {saved ? (
        <div role="status" className="people-change">
          {done(review.receipt)}
        </div>
      ) : (
        <form id={formId} onSubmit={next} noValidate>
          {reviewing ? (
            <>
              <PlanReview
                plan={review.plan}
                checking={review.phase === "checking"}
                problem={review.problem}
                reason={reason}
                onReason={setReason}
              />
              {reviewControls?.(review.plan)}
            </>
          ) : (
            details
          )}
          {problem && (
            <p className="people-change__problem" role="alert">
              {problem}
            </p>
          )}
        </form>
      )}
    </Dialog>
  );
}
