import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api";
import { Button, Card, Dialog } from "../../ui";

type JoinRequestItem = {
  id: string;
  created_at: string;
  full_name: string;
  username: string;
  employee_no: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  designation: string | null;
  unit_id: string | null;
  unit_name: string | null;
  statement_of_interest: string | null;
  status: "pending" | "approved" | "rejected";
  reviewed_at: string | null;
  reviewed_by: string | null;
  review_note: string | null;
  created_user_id: string | null;
};

type JoinRequestsResponse = {
  requests: JoinRequestItem[];
  counts: {
    pending: number;
    approved: number;
    rejected: number;
    total: number;
  };
};

type ApprovedSlip = {
  code: string;
  expires_at: string;
  fullName: string;
  username: string;
};

type FilterStatus = "all" | "pending" | "approved" | "rejected";

export function JoinRequestsView({ onCountChange }: { onCountChange?: (count: number) => void }) {
  const [filter, setFilter] = useState<FilterStatus>("pending");
  const [data, setData] = useState<JoinRequestsResponse | null>(null);
  const [availableUnits, setAvailableUnits] = useState<{ id: string; name: string; kind: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Review & Verify state
  const [reviewingItem, setReviewingItem] = useState<JoinRequestItem | null>(null);
  const [verifiedName, setVerifiedName] = useState("");
  const [verifiedEmp, setVerifiedEmp] = useState("");
  const [verifiedDesig, setVerifiedDesig] = useState("");
  const [verifiedUnitId, setVerifiedUnitId] = useState("");
  const [verifiedCustomUnit, setVerifiedCustomUnit] = useState("");
  const [approveBusy, setApproveBusy] = useState(false);

  // Activation slip modal state
  const [activeSlip, setActiveSlip] = useState<ApprovedSlip | null>(null);
  const [copied, setCopied] = useState(false);

  // Reject state
  const [rejectingItem, setRejectingItem] = useState<JoinRequestItem | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectBusy, setRejectBusy] = useState(false);

  function loadRequests() {
    setLoading(true);
    setError(null);
    api<JoinRequestsResponse>(`/admin/join-requests?status=${filter}`)
      .then((res) => {
        setData(res);
        setLoading(false);
        if (onCountChange) {
          onCountChange(res.counts.pending);
        }
      })
      .catch((err) => {
        setError(errorMessage(err));
        setLoading(false);
      });
  }

  useEffect(() => {
    loadRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reloads when the status filter changes
  }, [filter]);

  useEffect(() => {
    api<{ units: { id: string; name: string; kind: string }[] }>("/join-requests/units")
      .then((res) => setAvailableUnits(res.units))
      .catch(() => {});
  }, []);

  function startReview(item: JoinRequestItem) {
    setReviewingItem(item);
    setVerifiedName(item.full_name);
    setVerifiedEmp(item.employee_no || "");
    setVerifiedDesig(item.designation || "");
    if (item.unit_id) {
      setVerifiedUnitId(item.unit_id);
      setVerifiedCustomUnit("");
    } else if (item.unit_name) {
      const match = availableUnits.find((u) => u.name.toLowerCase() === item.unit_name?.toLowerCase());
      if (match) {
        setVerifiedUnitId(match.id);
        setVerifiedCustomUnit("");
      } else {
        setVerifiedUnitId("NEW");
        setVerifiedCustomUnit(item.unit_name);
      }
    } else {
      setVerifiedUnitId(availableUnits[0]?.id || "NEW");
      setVerifiedCustomUnit("");
    }
  }

  async function handleConfirmApprove() {
    if (!reviewingItem) return;
    setApproveBusy(true);
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

      const currentItem = reviewingItem;
      setReviewingItem(null);
      setActiveSlip({
        code: res.activation.code,
        expires_at: res.activation.expires_at,
        fullName: currentItem.full_name,
        username: currentItem.username,
      });
      loadRequests();
    } catch (err: unknown) {
      alert(errorMessage(err));
    } finally {
      setApproveBusy(false);
    }
  }

  async function handleConfirmReject() {
    if (!rejectingItem) return;
    setRejectBusy(true);
    try {
      await api(`/admin/join-requests/${rejectingItem.id}/reject`, {
        method: "POST",
        body: { reason: rejectReason.trim() || "Declined by administrator" },
      });
      setRejectingItem(null);
      setRejectReason("");
      loadRequests();
    } catch (err: unknown) {
      alert(errorMessage(err));
    } finally {
      setRejectBusy(false);
    }
  }

  function copyCode() {
    if (!activeSlip) return;
    navigator.clipboard.writeText(activeSlip.code).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      },
      () => setCopied(false),
    );
  }

  return (
    <div className="join-requests-view" role="region" aria-label="Voluntary join applications">
      {/* Top Filter Tabs */}
      <div className="join-requests-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={filter === "pending"}
          className={`join-requests-tab ${filter === "pending" ? "join-requests-tab--active" : ""}`}
          onClick={() => setFilter("pending")}
        >
          Pending Review {data ? `(${data.counts.pending})` : ""}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={filter === "approved"}
          className={`join-requests-tab ${filter === "approved" ? "join-requests-tab--active" : ""}`}
          onClick={() => setFilter("approved")}
        >
          Approved {data ? `(${data.counts.approved})` : ""}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={filter === "rejected"}
          className={`join-requests-tab ${filter === "rejected" ? "join-requests-tab--active" : ""}`}
          onClick={() => setFilter("rejected")}
        >
          Declined {data ? `(${data.counts.rejected})` : ""}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={filter === "all"}
          className={`join-requests-tab ${filter === "all" ? "join-requests-tab--active" : ""}`}
          onClick={() => setFilter("all")}
        >
          All Applications {data ? `(${data.counts.total})` : ""}
        </button>
      </div>

      {loading && <p className="join-requests-muted">Loading applications…</p>}
      {error && (
        <p className="join-requests-error" role="alert">
          ⚠️ {error}
        </p>
      )}

      {!loading && data && data.requests.length === 0 && (
        <Card>
          <div className="join-requests-empty">
            <span className="join-requests-empty__icon" aria-hidden="true">
              📭
            </span>
            <p className="join-requests-empty__title">No {filter} applications</p>
            <p className="join-requests-empty__desc">
              When laboratory staff submit voluntary requests to join LabAdda from the sign-in page, they will
              appear here for verification and account activation.
            </p>
          </div>
        </Card>
      )}

      {/* Applications Cards List */}
      <div className="join-requests-list">
        {data?.requests.map((item) => (
          <div key={item.id} className="join-request-card">
            <div className="join-request-card__head">
              <div>
                <h3 className="join-request-card__name">{item.full_name}</h3>
                <span className="join-request-card__username">@{item.username}</span>
              </div>

              <div className="join-request-card__status-wrap">
                <span className={`join-status-pill join-status-pill--${item.status}`}>
                  {item.status.toUpperCase()}
                </span>
                <span className="join-request-card__date">
                  Applied {new Date(item.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>

            <div className="join-request-card__grid">
              <div className="join-request-meta">
                <span className="join-request-meta__label">Employee ID</span>
                <span className="join-request-meta__val">{item.employee_no || "Not specified"}</span>
              </div>
              <div className="join-request-meta">
                <span className="join-request-meta__label">Designation</span>
                <span className="join-request-meta__val">{item.designation || "Not specified"}</span>
              </div>
              <div className="join-request-meta">
                <span className="join-request-meta__label">Division / Unit</span>
                <span className="join-request-meta__val">
                  {item.unit_name || "General Laboratory"}
                  {!item.unit_id ? (
                    <span className="join-unit-tag join-unit-tag--new">New / Unlisted</span>
                  ) : null}
                </span>
              </div>
              <div className="join-request-meta">
                <span className="join-request-meta__label">Official Email</span>
                <span className="join-request-meta__val">{item.contact_email || "Not specified"}</span>
              </div>
              {item.contact_phone && (
                <div className="join-request-meta">
                  <span className="join-request-meta__label">Phone / Intercom</span>
                  <span className="join-request-meta__val">{item.contact_phone}</span>
                </div>
              )}
            </div>

            {item.statement_of_interest && (
              <div className="join-request-card__interest">
                <span className="join-request-meta__label">Research Interest / Purpose:</span>
                <p className="join-request-card__interest-text">{item.statement_of_interest}</p>
              </div>
            )}

            {item.status === "rejected" && item.review_note && (
              <div className="join-request-card__rejection">
                <strong>Decline note:</strong> {item.review_note}
              </div>
            )}

            {/* Action Buttons for Pending Applications */}
            {item.status === "pending" && (
              <div className="join-request-card__actions">
                <Button variant="primary" onClick={() => startReview(item)}>
                  ✓ Review, Verify & Approve
                </Button>
                <Button
                  variant="quiet"
                  onClick={() => {
                    setRejectingItem(item);
                    setRejectReason("");
                  }}
                >
                  Decline…
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Review & Verify Approval Modal */}
      {reviewingItem && (
        <Dialog
          open={Boolean(reviewingItem)}
          title="Verify & Approve Membership Application"
          onClose={() => setReviewingItem(null)}
        >
          <div className="review-modal-body">
            <p className="review-modal-intro">
              Verify the applicant's official records before creating their account. You may adjust their
              personnel details or assigned division/group below.
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
                  id="rev-email"
                  type="text"
                  className="join-form__input"
                  value={reviewingItem.contact_email || "Not specified"}
                  disabled
                />
              </div>

              <div className="join-form__field join-form__field--full">
                <label htmlFor="rev-unit" className="join-form__label">
                  Assigned Division or Section:
                </label>
                <select
                  id="rev-unit"
                  className="join-form__select"
                  value={verifiedUnitId}
                  onChange={(e) => setVerifiedUnitId(e.target.value)}
                >
                  {availableUnits.length > 0 && (
                    <optgroup label="Available Units">
                      {availableUnits.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.name}
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

            <div className="join-form__actions">
              <Button variant="quiet" onClick={() => setReviewingItem(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                busy={approveBusy}
                busyLabel="Creating Account…"
                onClick={handleConfirmApprove}
              >
                ✓ Confirm & Issue Activation Code
              </Button>
            </div>
          </div>
        </Dialog>
      )}

      {/* Activation Slip Modal */}
      {activeSlip && (
        <Dialog
          open={Boolean(activeSlip)}
          title="Account Created & Activation Code Issued"
          onClose={() => setActiveSlip(null)}
        >
          <div className="activation-modal-slip">
            <p className="activation-modal-slip__intro">
              An account has been created for <strong>{activeSlip.fullName}</strong> (
              <code>@{activeSlip.username}</code>).
            </p>
            <div className="activation-modal-slip__box">
              <span className="activation-modal-slip__label">One-Time Activation Code</span>
              <div className="activation-modal-slip__code-row">
                <span className="activation-modal-slip__code">{activeSlip.code}</span>
                <Button onClick={copyCode}>{copied ? "Copied!" : "Copy code"}</Button>
              </div>
            </div>
            <p className="activation-modal-slip__note">
              Provide this code to the user. They can open <code>/activate</code> on the intranet to set their
              password and begin collaborating.
            </p>
            <div className="activation-modal-slip__actions">
              <Button variant="primary" onClick={() => setActiveSlip(null)}>
                Done
              </Button>
            </div>
          </div>
        </Dialog>
      )}

      {/* Reject Reason Dialog */}
      {rejectingItem && (
        <Dialog
          open={Boolean(rejectingItem)}
          title="Decline Membership Application"
          onClose={() => setRejectingItem(null)}
        >
          <div className="reject-modal-body">
            <p>
              Decline voluntary application for <strong>{rejectingItem.full_name}</strong> (
              <code>@{rejectingItem.username}</code>)?
            </p>
            <div className="join-form__field">
              <label htmlFor="reject-reason" className="join-form__label">
                Reason / Internal Note:
              </label>
              <input
                id="reject-reason"
                type="text"
                className="join-form__input"
                placeholder="e.g. Could not verify lab affiliation"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
              />
            </div>
            <div className="join-form__actions">
              <Button variant="quiet" onClick={() => setRejectingItem(null)}>
                Cancel
              </Button>
              <Button variant="danger" busy={rejectBusy} busyLabel="Declining…" onClick={handleConfirmReject}>
                Decline Application
              </Button>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}
