import { useEffect, useState } from "react";
import { InventoryJobs } from "../components/InventoryJobs";
import { DatabaseStorage } from "../components/DatabaseStorage";
import { LogicalCharges } from "../components/LogicalCharges";
import { api, errorMessage } from "../api";
import type { SiteUsage } from "../governance-types";
import { fmtBytes, fmtTime } from "../format";
import { Button, Card, ErrorState, Skeleton } from "../ui";
import "../components/storage.css";

export function Operations() {
  const [data, setData] = useState<SiteUsage | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setData(null);
    setError("");
    try {
      setData(await api<SiteUsage>("/admin/usage"));
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <section className="storage-stack">
      <h2 className="storage-heading">Operational storage observations</h2>
      <p>Read-only metadata. Operational access grants no private content or administration rights.</p>
      <div>
        <Button icon="refresh" onClick={load}>
          Refresh operational observations
        </Button>
      </div>
      {error && <ErrorState message={error} title="Observations could not be loaded" />}
      {!data && !error && <Skeleton lines={4} label="Loading observations…" />}
      {data && (
        <Card title="Partial site measurement" level={3}>
          <div className="storage-section">
            <dl className="storage-list">
              <dt>Tracked original files</dt>
              <dd>
                {data.assets.tracked_files} · {fmtBytes(data.assets.tracked_original_bytes)}
              </dd>
              <dt>Previews with recorded measurements</dt>
              <dd>{fmtBytes(data.assets.tracked_preview_bytes ?? null)}</dd>
              <dt>Previews with unknown measurements</dt>
              <dd>{data.assets.unknown_preview_files ?? "Unknown"}</dd>
              <dt>Pending original-byte reservations</dt>
              <dd>{fmtBytes(data.assets.pending_upload_original_bytes)}</dd>
              <dt>Asset filesystem free space</dt>
              <dd>
                {fmtBytes(data.filesystem.free_bytes)} · {data.filesystem.state}
              </dd>
              <dt>Observed</dt>
              <dd>{fmtTime(data.assets.observed_at)}</dd>
            </dl>
            <LogicalCharges charges={data.logical_charges} scope="site" />
            <DatabaseStorage storage={data.database} />
            <p>
              Historical previews without expected measurements, other derivatives, non-upload reservations,
              trash and temporary archives are not fully measured. Preview metadata is not a current disk
              inspection. No configured site budget or enforcement authority.
            </p>
          </div>
        </Card>
      )}
      <InventoryJobs />
    </section>
  );
}
