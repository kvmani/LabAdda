import { useState, type ReactNode } from "react";
import { errorMessage } from "../api";
import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { TextArea } from "./TextArea";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  /** Plain sentences naming who and what is affected and what changes for them (UX-07). */
  consequences: ReactNode[];
  /** Repeats the action and its object, for example "Retire 1 person". */
  confirmLabel: string;
  onConfirm: (reason: string) => Promise<void> | void;
  onCancel: () => void;
  /** Ask for a reason that is sent with the change and kept in the audit trail. */
  requireReason?: boolean;
  reasonLabel?: string;
  minReasonLength?: number;
  danger?: boolean;
};

/** Confirms an action that changes access or cannot be undone, saying exactly what will happen. */
export function ConfirmDialog({
  open,
  title,
  consequences,
  confirmLabel,
  onConfirm,
  onCancel,
  requireReason = false,
  reasonLabel = "Reason",
  minReasonLength = 3,
  danger = false,
}: ConfirmDialogProps) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reasonMissing = requireReason && reason.trim().length < minReasonLength;

  async function confirm() {
    if (reasonMissing || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
      setReason("");
    } catch (failure: unknown) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      title={title}
      onClose={busy ? () => undefined : onCancel}
      size="sm"
      footer={
        <>
          <Button variant="quiet" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            onClick={() => void confirm()}
            disabled={reasonMissing}
            busy={busy}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <ul className="ui-confirm__consequences">
        {consequences.map((consequence, index) => (
          <li key={index}>{consequence}</li>
        ))}
      </ul>
      {requireReason && (
        <TextArea
          label={reasonLabel}
          hint={`At least ${minReasonLength} characters. Kept in the audit trail.`}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          required
          rows={3}
          data-autofocus
        />
      )}
      {error && (
        <p className="ui-confirm__error" role="alert">
          {error}
        </p>
      )}
    </Dialog>
  );
}
