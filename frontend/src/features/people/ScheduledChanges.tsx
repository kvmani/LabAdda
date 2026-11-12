import { useState } from "react";
import { api, errorMessage } from "../../api";
import { Banner, Button, ConfirmDialog, ErrorState, Skeleton, Tag } from "../../ui";
import { calendarDate } from "./model";
import { usePeopleData } from "./usePeopleData";
import type { ScheduledItem } from "./changeTypes";

const KIND_WORDS: Record<string, string> = {
  edit_person: "Edit details",
  transfer: "Transfer",
  promote: "Promotion",
  change_authority: "Change of Head or Deputy",
  additional_charge: "Additional charge",
  leave: "Leave",
  return: "Return from leave",
  retire: "Retirement or departure",
  suspend: "Suspension",
  unit_create: "New unit",
  unit_rename: "Rename unit",
  unit_move: "Move unit",
  unit_merge: "Merge units",
  unit_split: "Split unit",
  unit_close: "Close unit",
  unit_reopen: "Reopen unit",
};

type Props = {
  /** Show only the changes about one person (their profile); omit for the People overview. */
  personId?: string;
  onDenied: () => void;
  /** Called after a cancellation so other lists can refresh. */
  onChanged?: () => void;
};

/** Changes waiting for their day or for review, each cancellable with a reason. */
export function ScheduledChanges({ personId, onDenied, onChanged }: Props) {
  const list = usePeopleData<{ items: ScheduledItem[] }>(
    `/admin/changes/scheduled${personId ? "?person_id=" + encodeURIComponent(personId) : ""}`,
    onDenied,
  );
  const [cancelling, setCancelling] = useState<ScheduledItem | null>(null);
  const [problem, setProblem] = useState("");
  const heading = personId ? "Scheduled changes for this person" : "Scheduled changes";
  if (list.error) return <ErrorState message={list.error} onRetry={list.refresh} />;
  if (list.loading) return <Skeleton lines={2} />;
  const items = list.data?.items ?? [];
  if (!items.length && personId) return null;

  async function cancel(reason: string) {
    if (!cancelling) return;
    try {
      await api(`/admin/changes/scheduled/${cancelling.id}`, { method: "DELETE", params: { reason } });
      setCancelling(null);
      list.refresh();
      onChanged?.();
    } catch (error: unknown) {
      setProblem(errorMessage(error));
      throw error;
    }
  }

  return (
    <section aria-label={heading} className="people-scheduled">
      <h3 className="people-change__heading">{heading}</h3>
      {problem && <Banner level="warning">{problem}</Banner>}
      {items.length ? (
        <ul className="people-history">
          {items.map((item) => (
            <li key={item.id}>
              <strong>
                {KIND_WORDS[item.kind] ?? "Change"} on {calendarDate(item.effective_on)}
              </strong>{" "}
              {item.state === "needs_review" ? (
                <Tag tone="warn">Needs review</Tag>
              ) : (
                <Tag tone="neutral">Waiting</Tag>
              )}
              {item.steps.length > 0 && (
                <ul>
                  {item.steps.map((step, index) => (
                    <li key={index}>{step}</li>
                  ))}
                </ul>
              )}
              {item.note && <p role="note">{item.note}</p>}
              <span>
                Scheduled by {item.created_by}. Reason: {item.reason}
              </span>
              <br />
              <Button variant="quiet" onClick={() => setCancelling(item)}>
                {item.state === "needs_review" ? "Dismiss this change" : "Cancel this change"}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p>No changes are scheduled.</p>
      )}
      <ConfirmDialog
        open={cancelling !== null}
        title="Cancel scheduled change"
        consequences={[
          "Nothing will be applied on that day.",
          "To make the change later, schedule it again.",
        ]}
        confirmLabel="Cancel this change"
        requireReason
        onConfirm={cancel}
        onCancel={() => setCancelling(null)}
      />
    </section>
  );
}
