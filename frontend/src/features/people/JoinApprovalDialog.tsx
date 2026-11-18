import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { Button, Dialog } from "../../ui";
import type { ApprovedSlip, JoinRequestItem } from "./joinRequestTypes";
type Unit = { id: string; name: string; kind: string };
type Props = {
  reviewingItem: JoinRequestItem;
  availableUnits: Unit[];
  onClose: () => void;
  onApproved: (slip: ApprovedSlip) => void;
};
function initialUnit(item: JoinRequestItem, units: Unit[]): string {
  if (item.unit_id && units.some((unit) => unit.id === item.unit_id)) return item.unit_id;
  if (item.unit_name) {
    const matches = units.filter((unit) => unit.name.toLowerCase() === item.unit_name?.toLowerCase());
    return matches.length === 1 ? matches[0]!.id : "NEW";
  }
  return "";
}
export function JoinApprovalDialog({ reviewingItem, availableUnits, onClose, onApproved }: Props) {
  const [verifiedName, setVerifiedName] = useState(reviewingItem.full_name);
  const [verifiedEmp, setVerifiedEmp] = useState(reviewingItem.employee_no || "");
  const [verifiedDesig, setVerifiedDesig] = useState(reviewingItem.designation || "");
  const [verifiedUnitId, setVerifiedUnitId] = useState(() => initialUnit(reviewingItem, availableUnits));
  const [verifiedCustomUnit, setVerifiedCustomUnit] = useState(reviewingItem.unit_name || "");
  const [approveBusy, setApproveBusy] = useState(false);
  const [reviewError, setReviewError] = useState("");
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  async function handleConfirmApprove() {
    setApproveBusy(true);
    setReviewError("");
    try {
      const res = await api<{
        status: string;
        activation: { code: string; expires_at: string };
        user: { id: string; username: string; display_name: string };
      }>(`/admin/join-requests/${reviewingItem.id}/approve`, {
        method: "POST",
        body: {
          full_name: verifiedName.trim() || reviewingItem.full_name,
          employee_no: verifiedEmp.trim() || null,
          designation: verifiedDesig.trim() || null,
          unit_id: verifiedUnitId === "NEW" ? null : verifiedUnitId,
          custom_unit_name: verifiedUnitId === "NEW" ? verifiedCustomUnit.trim() : null,
        },
      });

      if (!active.current) return;
      onApproved({
        code: res.activation.code,
        expires_at: res.activation.expires_at,
        fullName: res.user.display_name,
        username: res.user.username,
      });
    } catch (err: unknown) {
      if (active.current) setReviewError(errorMessage(err));
    } finally {
      if (active.current) setApproveBusy(false);
    }
  }

  return (
    <Dialog
      open={true}
      title="Verify & Approve Membership Application"
      onClose={() => {
        if (!approveBusy) onClose();
      }}
    >
      <div className="review-modal-body">
        <p className="review-modal-intro">
          Verify the applicant's official records before creating their account. You may adjust their
          personnel details or assigned organisation unit below.
        </p>

        <div className="review-modal-grid">
          <div className="join-form__field">
            <label htmlFor="rev-name" className="join-form__label">
              Full Name (Official):
            </label>
            <input
              id="rev-name"
              type="text"
              className="join-form__input"
              value={verifiedName}
              onChange={(e) => setVerifiedName(e.target.value)}
              required
            />
          </div>

          <div className="join-form__field">
            <label htmlFor="rev-emp" className="join-form__label">
              Staff / Employee ID:
            </label>
            <input
              id="rev-emp"
              type="text"
              className="join-form__input"
              value={verifiedEmp}
              onChange={(e) => setVerifiedEmp(e.target.value)}
              placeholder="e.g. EMP-4102"
            />
          </div>

          <div className="join-form__field">
            <label htmlFor="rev-desig" className="join-form__label">
              Designation / Role:
            </label>
            <input
              id="rev-desig"
              type="text"
              className="join-form__input"
              value={verifiedDesig}
              onChange={(e) => setVerifiedDesig(e.target.value)}
              placeholder="e.g. Senior Scientist"
            />
          </div>

          <div className="join-form__field">
            <label htmlFor="rev-email" className="join-form__label">
              Intranet Email (Read-only):
            </label>
            <input
              type="text"
              className="join-form__input"
              id="rev-email"
              value={reviewingItem.contact_email || "Not specified"}
              disabled
            />
          </div>

          <div className="join-form__field join-form__field--full">
            <label htmlFor="rev-unit" className="join-form__label">
              Assigned Organisation Unit:
            </label>
            <select
              id="rev-unit"
              className="join-form__select"
              value={verifiedUnitId}
              onChange={(e) => setVerifiedUnitId(e.target.value)}
            >
              <option value="">Choose the verified organisation unit</option>
              {availableUnits.length > 0 && (
                <optgroup label="Available Organisation Units">
                  {availableUnits.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name} ({u.kind === "org" ? "Org Unit" : "Group"})
                    </option>
                  ))}
                </optgroup>
              )}
              <option value="NEW">➕ Register as New Lab Unit in Database</option>
            </select>
            <p className="join-form__hint">Selecting an existing unit prevents duplicates and typos.</p>
          </div>

          {verifiedUnitId === "NEW" && (
            <div className="join-form__field join-form__field--full join-form__field--highlight">
              <label htmlFor="rev-custom-unit" className="join-form__label">
                New Unit Name to Register:
              </label>
              <input
                id="rev-custom-unit"
                type="text"
                className="join-form__input"
                value={verifiedCustomUnit}
                onChange={(e) => setVerifiedCustomUnit(e.target.value)}
                placeholder="e.g. Surface Engineering Division"
                required
              />
              <p className="join-form__hint">
                This unit will be created under the organization root and will be available in future
                dropdowns.
              </p>
            </div>
          )}
        </div>

        {reviewError && (
          <p role="alert" className="join-requests-error">
            {reviewError}
          </p>
        )}
        <div className="join-form__actions">
          <Button variant="quiet" disabled={approveBusy} onClick={() => onClose()}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={
              !verifiedUnitId ||
              verifiedName.trim().length < 2 ||
              (verifiedUnitId === "NEW" && !verifiedCustomUnit.trim())
            }
            busy={approveBusy}
            busyLabel="Creating Account…"
            onClick={handleConfirmApprove}
          >
            ✓ Confirm & Issue Activation Code
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
