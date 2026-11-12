import { useState } from "react";
import { Button, Dialog } from "../../ui";
import { SlipCard } from "./ActivationSlip";
import { PlanReview } from "./PlanReview";
import { useBulkReview } from "./useBulkReview";
import type { BulkItem } from "./changeTypes";

type Props = {
  title: string;
  requests: BulkItem[];
  onClose: () => void;
  onBack?: () => void;
  onDenied: () => void;
  onDone: () => void;
};

/** Review many changes as one plan, give one reason, apply together; new people get printable slips. */
export function BulkReviewDialog({ title, requests, onClose, onBack, onDenied, onDone }: Props) {
  const review = useBulkReview(requests, onDenied);
  const [reason, setReason] = useState("");
  const [short, setShort] = useState(false);
  const saved = review.phase === "saved";
  const busy = review.phase === "saving";
  const blocked = Boolean(review.plan?.blockers.length);

  function apply() {
    if (reason.trim().length < 3) return setShort(true);
    setShort(false);
    void review.confirm(reason.trim());
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
      {onBack && (
        <Button onClick={onBack} disabled={busy}>
          Back
        </Button>
      )}
      <Button
        variant="primary"
        onClick={apply}
        busy={busy}
        busyLabel="Applying…"
        disabled={!review.plan || blocked}
      >
        {`Apply ${requests.length} ${requests.length === 1 ? "change" : "changes"}`}
      </Button>
    </>
  );
  return (
    <Dialog open title={title} onClose={busy ? () => undefined : finish} size="lg" footer={footer}>
      {saved && review.receipt ? (
        <div role="status" className="people-change">
          <p>
            {review.receipt.count} {review.receipt.count === 1 ? "change was" : "changes were"} applied.
          </p>
          {review.receipt.added.length > 0 && (
            <>
              <p>
                Activation codes are shown only once. Print the slips now and hand each one to its person
                privately.
              </p>
              <div className="people-slips">
                {review.receipt.added.map((person) => (
                  <SlipCard
                    key={person.person_id}
                    displayName={person.display_name}
                    username={person.username}
                    code={person.activation.code}
                    expiresAt={person.activation.expires_at}
                    label={`Activation slip for ${person.display_name}`}
                  />
                ))}
              </div>
              <Button icon="download" onClick={() => window.print()}>
                Print all activation slips
              </Button>
            </>
          )}
        </div>
      ) : (
        <>
          <PlanReview
            plan={review.plan}
            checking={review.phase === "checking"}
            problem={review.problem}
            reason={reason}
            onReason={setReason}
          />
          {short && (
            <p className="people-change__problem" role="alert">
              Give a reason of at least 3 characters.
            </p>
          )}
        </>
      )}
    </Dialog>
  );
}
