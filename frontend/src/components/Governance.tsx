import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { InventoryJobs } from "./InventoryJobs";
import { DatabaseStorage } from "./DatabaseStorage";
import { LogicalCharges } from "./LogicalCharges";
import { api, asApiError, errorMessage } from "../api";
import { fmtBytes as bytes } from "../format";
import type {
  CapacityForecast as Forecast,
  CapacityProfile,
  PolicyDrafts,
  SiteUsage,
  Observation,
} from "../governance-types";
import { CapacityForecast } from "./CapacityForecast";
import { InspectionReceipts, type StorageReceipt } from "./InspectionReceipts";
import { ProposalHistory } from "./ProposalHistory";
import { Button, Card, ErrorState, Skeleton, TextArea, TextInput } from "../ui";
import "./storage.css";

const MiB = 1024 * 1024;
export function Governance() {
  const [policy, setPolicy] = useState<PolicyDrafts | null>(null);
  const [usage, setUsage] = useState<SiteUsage | null>(null);
  const [inspections, setInspections] = useState<StorageReceipt[]>([]);
  const [history, setHistory] = useState<Observation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [fileLimit, setFileLimit] = useState(20);
  const [userLimit, setUserLimit] = useState(500);
  const [workspaceLimit, setWorkspaceLimit] = useState(2048);
  const [siteLimit, setSiteLimit] = useState("");
  const [reserve, setReserve] = useState(2048);
  const [reservePercent, setReservePercent] = useState(10);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const forecastGeneration = useRef(0);
  function invalidateForecast() {
    forecastGeneration.current++;
    setForecast(null);
  }
  function proposedProfile(): CapacityProfile {
    return {
      schema_version: 2,
      mode: "observation",
      max_attachment_bytes: fileLimit * MiB,
      user_quota_bytes: userLimit * MiB,
      workspace_quota_bytes: workspaceLimit * MiB,
      site_asset_budget_bytes: siteLimit === "" ? null : Number(siteLimit) * MiB,
      filesystem_reserve_bytes: reserve * MiB,
      filesystem_reserve_percent: reservePercent,
    };
  }
  async function preview() {
    const generation = ++forecastGeneration.current;
    setForecast(null);
    setError(null);
    setMessage("");
    setBusy(true);
    try {
      const result = await api<Forecast>("/admin/capacity-forecasts", {
        body: { profile: proposedProfile() },
      });
      if (generation === forecastGeneration.current) setForecast(result);
    } catch (e: unknown) {
      if (generation === forecastGeneration.current)
        setError((asApiError(e)?.fields ?? []).map((field) => field.message).join("; ") || errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function load() {
    invalidateForecast();
    const [p, u, h, inspections] = await Promise.all([
      api<PolicyDrafts>("/admin/policy-drafts"),
      api<SiteUsage>("/admin/usage"),
      api<{ observations: Observation[] }>("/admin/usage-observations"),
      api<{ inspections: StorageReceipt[] }>("/admin/storage-inspections"),
    ]);
    setPolicy(p);
    setUsage(u);
    setHistory(h.observations);
    setInspections(inspections.inspections);
  }
  useEffect(() => {
    load().catch((e) => setError(errorMessage(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when the panel opens
  }, []);
  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      await action();
      await load();
      setMessage(success);
    } catch (e: unknown) {
      const fields = asApiError(e)?.fields ?? [];
      setError(
        fields.length
          ? fields.map((field) => `${field.field}: ${field.message}`).join("; ")
          : errorMessage(e),
      );
    } finally {
      setBusy(false);
    }
  }
  async function propose(e: FormEvent) {
    e.preventDefault();
    invalidateForecast();
    await run(
      () =>
        api("/admin/policy-drafts", {
          body: {
            base_revision: policy!.latest_revision,
            reason,
            profile: proposedProfile(),
          },
        }),
      "Proposal saved. No limits or retention rules were activated.",
    );
  }
  const limit = (set: (value: number) => void) => (e: ChangeEvent<HTMLInputElement>) => {
    invalidateForecast();
    set(Number(e.target.value));
  };
  return (
    <div className="storage-stack">
      <h2 className="storage-heading">Storage observations and policy proposals</h2>
      <p>
        Foundation preview: saving proposals cannot activate enforcement or delete data. Current pilot limits
        remain environment-controlled.
      </p>
      {error && (
        <ErrorState message={`${error} Reload observations before retrying a conflicted proposal.`} />
      )}
      {message && <p role="status">{message}</p>}
      <div>
        <Button icon="refresh" disabled={busy} onClick={() => run(async () => {}, "Observations refreshed.")}>
          Reload observations
        </Button>
      </div>
      {!policy && !error && <Skeleton lines={4} label="Loading governance information…" />}
      {usage && (
        <Card title="Site measurements (partial)" level={3}>
          <div className="storage-section">
            <dl className="storage-list">
              <dt>Tracked original file bytes</dt>
              <dd>
                {bytes(usage.assets.tracked_original_bytes)} · {usage.assets.tracked_files} files
              </dd>
              <dt>Pending original-byte reservations</dt>
              <dd>{bytes(usage.assets.pending_upload_original_bytes)}</dd>
              <dt>Previews with recorded measurements</dt>
              <dd>{bytes(usage.assets.tracked_preview_bytes ?? null)}</dd>
              <dt>Previews with unknown measurements</dt>
              <dd>{usage.assets.unknown_preview_files ?? "Unknown"}</dd>
              <dt>Asset filesystem free space</dt>
              <dd>
                {bytes(usage.filesystem.free_bytes)} · {usage.filesystem.state}
              </dd>
              <dt>Configured site budget</dt>
              <dd>Not configured</dd>
              <dt>Observed</dt>
              <dd>{new Date(usage.assets.observed_at).toLocaleString()}</dd>
            </dl>
            <LogicalCharges charges={usage.logical_charges} scope="site" />
            <DatabaseStorage storage={usage.database} />
            <p className="storage-note">
              Filesystem capacity may be shared with other services. Historical previews without expected
              measurements, other derivatives, non-upload reservations, trash and archive storage are not
              fully measured. Preview metadata is not a current disk inspection. These totals cannot approve
              enforcement or deletion.
            </p>
            <div>
              <Button
                disabled={busy}
                onClick={() =>
                  run(() => api("/admin/usage-observations", { body: {} }), "Partial observation recorded.")
                }
              >
                Record partial observation
              </Button>
            </div>
            <p>
              {Math.min(history.length, 5)} recent samples displayed; at most 100 operational samples
              retained.
            </p>
            {history.length > 0 && (
              <ul className="storage-steps">
                {history.slice(0, 5).map((h) => (
                  <li key={h.id}>
                    {new Date(h.observed_at).toLocaleString()} ·{" "}
                    {bytes(h.measurement.assets.tracked_original_bytes)} tracked originals
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      )}
      <InventoryJobs />
      <Card title="Storage inventories, inspections and reconciliations" level={3}>
        <div className="storage-section">
          <p>
            Asset-directory inventory receipts come from <code>labadda inventory-storage</code>. They report
            bounded metadata observations, including temporary and unreferenced candidates, without reading
            file contents.
          </p>
          <p>
            Run by the host operator with <code>labadda inspect-storage</code>. Inspections verify original
            hashes and preview hashes where expected measurements exist. Historical preview integrity remains
            unknown without those measurements. The scan time budget is cooperative, not a hard filesystem
            timeout. Inspections never repair files or authorize enforcement. A running record may be stale
            after an operator process stops.
          </p>
          <InspectionReceipts inspections={inspections} />
        </div>
      </Card>
      {policy && (
        <Card title={`Site proposal revision ${policy.latest_revision}`} level={3}>
          <div className="storage-section">
            <p>
              Current pilot file limit: {bytes(policy.runtime_limits.max_attachment_bytes)}. Current pilot
              user limit: {bytes(policy.runtime_limits.user_quota_bytes)}.
            </p>
            <form onSubmit={propose} className="storage-form">
              <TextInput
                label="Proposed file limit (MiB)"
                type="number"
                min="1"
                max="100"
                step="1"
                required
                value={fileLimit}
                onChange={limit(setFileLimit)}
              />
              <TextInput
                label="Proposed user limit (MiB)"
                type="number"
                min="1"
                max="102400"
                step="1"
                required
                value={userLimit}
                onChange={limit(setUserLimit)}
              />
              <TextInput
                label="Proposed workspace limit (MiB)"
                type="number"
                min="1"
                max="1024000"
                step="1"
                required
                value={workspaceLimit}
                onChange={limit(setWorkspaceLimit)}
              />
              <TextInput
                label="Proposed site asset budget (MiB; blank means not configured)"
                type="number"
                min="1"
                max="10485760"
                step="1"
                value={siteLimit}
                onChange={(e) => {
                  invalidateForecast();
                  setSiteLimit(e.target.value);
                }}
              />
              <TextInput
                label="Proposed filesystem reserve floor (MiB)"
                type="number"
                min="1"
                max="102400"
                step="1"
                required
                value={reserve}
                onChange={limit(setReserve)}
              />
              <TextInput
                label="Proposed filesystem reserve (%)"
                type="number"
                min="1"
                max="50"
                step="1"
                required
                value={reservePercent}
                onChange={limit(setReservePercent)}
              />
              <p>
                The proposed reserve is the greater of its floor and percentage of observed filesystem
                capacity. Preview estimates use originals, recorded previews and pending originals; other
                storage remains unmeasured.
              </p>
              <div>
                <Button disabled={busy} onClick={preview}>
                  Preview proposed capacity
                </Button>
              </div>
              {forecast && <CapacityForecast forecast={forecast} />}
              <TextArea
                label="Proposal reason"
                required
                minLength={3}
                maxLength={500}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <div>
                <Button variant="primary" type="submit" disabled={busy}>
                  Save non-enforcing proposal
                </Button>
              </div>
            </form>
            <ProposalHistory drafts={policy.drafts} />
          </div>
        </Card>
      )}
    </div>
  );
}
