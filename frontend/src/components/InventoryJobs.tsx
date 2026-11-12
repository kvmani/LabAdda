import { useEffect, useRef, useState } from "react";
import { invalidate } from "../generation";
import { api, errorMessage } from "../api";
import { Button, Card, ErrorState, Select, Skeleton } from "../ui";
import "./storage.css";

type Attempt = {
  number: number;
  state: string;
  heartbeat_at: string;
  finished_at: string | null;
  receipt_id: string | null;
};
type Job = {
  id: string;
  state: string;
  attempt: number;
  lease_expired: boolean;
  lease_until: string | null;
  updated_at: string;
  attempts: Attempt[];
};
type Page = { jobs: Job[]; next_cursor: string | null; observed_at: string };
const states = ["queued", "running", "completed", "partial", "failed", "paused", "cancelled"];
const guidance: Record<string, string> = {
  queued: "Waiting for the host operator to run this observation.",
  running: "A worker holds a lease. Refresh to inspect its current status.",
  completed: "The selected observation finished. This does not authorize enforcement or deletion.",
  partial:
    "The observation is incomplete. Ask the host operator to inspect its receipt and budgets before retrying.",
  failed: "The scan failed. Ask the host operator to inspect storage access and its diagnostic receipt.",
  paused:
    "Copied work was paused during recovery. The host operator must review it before an explicit retry.",
  cancelled:
    "Result acceptance is cancelled. A worker stops at its next checkpoint; blocked storage calls may take longer.",
};
const time = (value: string | null) => (value ? new Date(value).toLocaleString() : "Not recorded");
const status = (job: Job) => (job.lease_expired ? "Expired lease — investigation required" : job.state);

export function InventoryJobs() {
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState<Page | null>(null);
  const [detail, setDetail] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const generation = useRef(0),
    detailGeneration = useRef(0);
  async function load(before?: string) {
    const current = ++generation.current;
    ++detailGeneration.current;
    setPage(null);
    setDetail(null);
    setSelected(null);
    setError("");
    setDetailError("");
    setLoading(true);
    const query = new URLSearchParams({ limit: "10" });
    if (filter) query.set("state", filter);
    if (before) query.set("before", before);
    try {
      const result = await api<Page>("/admin/inventory-jobs?" + query.toString());
      if (current === generation.current) setPage(result);
    } catch (e: unknown) {
      if (current === generation.current) setError(errorMessage(e));
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }
  async function inspect(id: string) {
    const current = ++detailGeneration.current;
    setDetail(null);
    setDetailError("");
    setSelected(id);
    try {
      const result = await api<Job>("/admin/inventory-jobs/" + id);
      if (current === detailGeneration.current) setDetail(result);
    } catch (e: unknown) {
      if (current === detailGeneration.current) setDetailError(errorMessage(e));
    }
  }
  useEffect(() => {
    void load();
    return () => {
      invalidate(generation);
      invalidate(detailGeneration);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the state filter changes
  }, [filter]);
  return (
    <Card title="Inventory jobs" level={3}>
      <div className="storage-section">
        <p>
          Read-only operator job history. Retries start the scan again; they do not resume a complete
          inventory generation.
        </p>
        <div className="storage-actions">
          <Select
            label="Inventory job state"
            value={filter}
            onChange={(e) => {
              ++generation.current;
              ++detailGeneration.current;
              setPage(null);
              setDetail(null);
              setSelected(null);
              setFilter(e.target.value);
            }}
            options={[{ value: "", label: "All states" }, ...states.map((s) => ({ value: s, label: s }))]}
          />
          <Button icon="refresh" onClick={() => load()} disabled={loading}>
            Refresh inventory jobs
          </Button>
        </div>
        {loading && <Skeleton lines={3} label="Loading inventory jobs…" />}
        {error && <ErrorState message={error} title="Inventory jobs could not be loaded" />}
        {page && (
          <>
            <p className="storage-muted">
              Observed {time(page.observed_at)} · {page.jobs.length} jobs on this page; not a total count.
            </p>
            {page.jobs.length === 0 ? (
              <p>No inventory jobs match this state.</p>
            ) : (
              <ul className="storage-items">
                {page.jobs.map((job) => (
                  <li key={job.id}>
                    <p>
                      <strong>{status(job)}</strong> · Attempt {job.attempt} · Updated {time(job.updated_at)}
                    </p>
                    <p className="storage-id">Job {job.id}</p>
                    <div>
                      <Button size="sm" onClick={() => inspect(job.id)}>
                        View attempts for {job.id}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {page.next_cursor && (
              <div>
                <Button onClick={() => load(page.next_cursor!)}>Older inventory jobs</Button>
              </div>
            )}
          </>
        )}
        {selected && !detail && !detailError && <Skeleton lines={2} label="Loading job attempts…" />}
        {detailError && <ErrorState message={detailError} title="Job attempts could not be loaded" />}
        {detail && (
          <div className="storage-section" aria-label="Selected inventory job" role="group">
            <h4 className="storage-subheading">Selected inventory job</h4>
            <p className="storage-id">{detail.id}</p>
            <p>
              <strong>{status(detail)}</strong>
            </p>
            <p>
              {detail.lease_expired
                ? "The lease has expired. A running label does not prove an active worker or success. Ask the host operator to investigate before an explicit retry."
                : (guidance[detail.state] ?? "Unknown state. Ask the host operator to inspect the job.")}
            </p>
            <p>Lease ends: {time(detail.lease_until)}</p>
            {detail.attempts.length === 0 ? (
              <p>No execution attempts recorded.</p>
            ) : (
              <ol className="storage-steps">
                {detail.attempts.map((attempt) => (
                  <li key={attempt.number}>
                    <p>
                      Attempt {attempt.number}: {attempt.state} · Heartbeat {time(attempt.heartbeat_at)} ·
                      Finished {time(attempt.finished_at)}
                    </p>
                    <p className="storage-id">
                      {attempt.receipt_id
                        ? `Accepted receipt: ${attempt.receipt_id}`
                        : "No accepted result receipt."}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
