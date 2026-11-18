import { useCallback, useEffect, useRef, useState } from "react";
import { JoinApprovalDialog } from "./JoinApprovalDialog";
import { BASE } from "../../config";
import { api, errorMessage } from "../../api";
import { invalidate } from "../../generation";
import type { ApprovedSlip, FilterStatus, JoinRequestItem, JoinRequestsResponse } from "./joinRequestTypes";
import { Button, Card, Dialog } from "../../ui";

export function JoinRequestsView({ onCountChange }: { onCountChange?: (count: number) => void }) {
  const [filter, setFilter] = useState<FilterStatus>("pending");
  const [data, setData] = useState<JoinRequestsResponse | null>(null);
  const [availableUnits, setAvailableUnits] = useState<{ id: string; name: string; kind: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const generation = useRef(0);
  const countChanged = useRef(onCountChange);
  countChanged.current = onCountChange;
  const [reviewError, setReviewError] = useState("");
  const [copyError, setCopyError] = useState("");

  // Review & Verify state
  const [reviewingItem, setReviewingItem] = useState<JoinRequestItem | null>(null);
  // Activation slip modal state
  const [activeSlip, setActiveSlip] = useState<ApprovedSlip | null>(null);
  const [copied, setCopied] = useState(false);

  // Reject state
  const [rejectingItem, setRejectingItem] = useState<JoinRequestItem | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectBusy, setRejectBusy] = useState(false);

  const loadRequests = useCallback(
    async (offset = 0) => {
      const token = ++generation.current;
      setLoading(true);
      setError(null);
      try {
        const res = await api<JoinRequestsResponse>("/admin/join-requests", {
          params: { status: filter, offset },
        });
        if (token !== generation.current) return;
        setData((previous) => ({
          ...res,
          requests: offset && previous ? [...previous.requests, ...res.requests] : res.requests,
        }));
        countChanged.current?.(res.counts.pending);
      } catch (failure: unknown) {
        if (token === generation.current) {
          setData(null);
          setError(errorMessage(failure));
        }
      } finally {
        if (token === generation.current) setLoading(false);
      }
    },
    [filter],
  );
  useEffect(() => {
    setData(null);
    void loadRequests();
    return () => invalidate(generation);
  }, [loadRequests]);
  useEffect(() => {
    let active = true;
    api<{ units: { id: string; name: string; kind: string }[] }>("/join-requests/units")
      .then((res) => {
        if (active) setAvailableUnits(res.units);
      })
      .catch((failure) => {
        if (active) setError(errorMessage(failure));
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleConfirmReject() {
    if (!rejectingItem) return;
    setRejectBusy(true);
    setReviewError("");
    try {
      await api(`/admin/join-requests/${rejectingItem.id}/reject`, {
        method: "POST",
        body: { reason: rejectReason.trim() || "Declined by administrator" },
      });
      setRejectingItem(null);
      setRejectReason("");
      void loadRequests();
    } catch (err: unknown) {
      setReviewError(errorMessage(err));
    } finally {
      setRejectBusy(false);
    }
  }

  async function copyCode() {
    if (!activeSlip) return;
    setCopied(false);
    setCopyError("");
    try {
      await navigator.clipboard.writeText(activeSlip.code);
      setCopied(true);
    } catch {
      setCopyError("Copy was unavailable. Select the visible code and copy it manually.");
    }
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
                <Button variant="primary" onClick={() => setReviewingItem(item)}>
                  ✓ Review, Verify & Approve
                </Button>
                <Button
                  variant="quiet"
                  onClick={() => {
                    setReviewError("");
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

      {data?.next_offset !== null && data?.next_offset !== undefined && (
        <Button disabled={loading} onClick={() => void loadRequests(data.next_offset ?? 0)}>
          Load more applications
        </Button>
      )}
      {error && <Button onClick={() => void loadRequests()}>Retry applications</Button>}
      {/* Review & Verify Approval Modal */}
      {reviewingItem && (
        <JoinApprovalDialog
          key={reviewingItem.id}
          reviewingItem={reviewingItem}
          availableUnits={availableUnits}
          onClose={() => setReviewingItem(null)}
          onApproved={(slip) => {
            setReviewingItem(null);
            setCopied(false);
            setCopyError("");
            setActiveSlip(slip);
            void loadRequests();
          }}
        />
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
            {copyError && <p role="alert">{copyError}</p>}
            <p>Expires: {new Date(activeSlip.expires_at).toLocaleString()}</p>
            <p className="activation-modal-slip__note">
              Provide this code to the user. They can open{" "}
              <code>{`${window.location.origin}${BASE}/activate`}</code> on the intranet to set their password
              and begin collaborating.
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
          onClose={() => {
            if (!rejectBusy) setRejectingItem(null);
          }}
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
            {reviewError && (
              <p role="alert" className="join-requests-error">
                {reviewError}
              </p>
            )}
            <div className="join-form__actions">
              <Button variant="quiet" disabled={rejectBusy} onClick={() => setRejectingItem(null)}>
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
