import { useEffect, useState } from "react";
import { InventoryJobs } from "../components/InventoryJobs";
import { DatabaseStorage } from "../components/DatabaseStorage";
import { LogicalCharges } from "../components/LogicalCharges";
import { api } from "../api";
import type { SiteUsage } from "../governance-types";
import { fmtBytes } from "../format";

export function Operations() {
  const [data, setData] = useState<SiteUsage | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setData(null);
    setError("");
    try {
      setData(await api<SiteUsage>("/admin/usage"));
    } catch (e: any) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <section>
      <h1>Operational storage observations</h1>
      <p>Read-only metadata. Operational access grants no private content or administration rights.</p>
      <button onClick={load}>Refresh operational observations</button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">Loading observations…</p>}
      {data && (
        <div className="card">
          <h2>Partial site measurement</h2>
          <dl>
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
            <dd>{new Date(data.assets.observed_at).toLocaleString()}</dd>
          </dl>
          <LogicalCharges charges={data.logical_charges} scope="site" />
          <DatabaseStorage storage={data.database} />
          <p>
            Historical previews without expected measurements, other derivatives, non-upload reservations,
            trash and temporary archives are not fully measured. Preview metadata is not a current disk
            inspection. No configured site budget or enforcement authority.
          </p>
        </div>
      )}
      <InventoryJobs />
    </section>
  );
}
