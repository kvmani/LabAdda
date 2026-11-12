import { useState } from "react";
import { api, errorStatus } from "../../api";
import { Button, ConfirmDialog, Dialog } from "../../ui";
import { ActivationSlip } from "./ActivationSlip";
import type { StaffRecord } from "./types";

type Issued = { person_id: string; code: string; expires_at: string };

/** For an invited person whose slip was lost: a fresh code; earlier unused codes stop working. */
export function NewActivationCode({
  person,
  onDenied,
  onIssued,
}: {
  person: StaffRecord;
  onDenied: () => void;
  onIssued: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const [issued, setIssued] = useState<Issued | null>(null);
  async function issue(reason: string) {
    try {
      const result = await api<Issued>("/admin/changes/activation-code", {
        body: { person_id: person.id, reason },
      });
      setAsking(false);
      setIssued(result);
      onIssued();
    } catch (error: unknown) {
      if ([401, 403].includes(errorStatus(error) ?? 0)) onDenied();
      throw error;
    }
  }
  return (
    <>
      <Button icon="refresh" onClick={() => setAsking(true)}>
        Issue a new activation code
      </Button>
      <ConfirmDialog
        open={asking}
        title={`New activation code for ${person.display_name}`}
        consequences={[
          `${person.display_name} gets a new one-time activation code.`,
          "Any earlier code that has not been used stops working.",
        ]}
        confirmLabel="Issue new code"
        requireReason
        reasonLabel="Reason for a new code"
        onConfirm={issue}
        onCancel={() => setAsking(false)}
      />
      {issued && (
        <Dialog
          open
          title="New activation code"
          onClose={() => setIssued(null)}
          size="lg"
          footer={
            <Button variant="primary" onClick={() => setIssued(null)}>
              Done
            </Button>
          }
        >
          <ActivationSlip
            displayName={person.display_name}
            username={person.username}
            code={issued.code}
            expiresAt={issued.expires_at}
          />
        </Dialog>
      )}
    </>
  );
}
