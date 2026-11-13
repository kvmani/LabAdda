import { useEffect, useState } from "react";
import { LogicalCharges } from "../components/LogicalCharges";
import type { UserUsage } from "../governance-types";
import { fmtBytes as bytes, fmtTime } from "../format";
import { api, errorMessage } from "../api";
import { Button, Card, ErrorState, PageHeader, Skeleton } from "../ui";
import "./usage.css";

export function Usage() {
  const [data, setData] = useState<UserUsage | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function load() {
    setError(null);
    try {
      setData(await api<UserUsage>("/usage"));
    } catch (e: unknown) {
      setError(errorMessage(e));
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <section className="usage">
      <PageHeader
        title="My storage usage"
        scope="These counters cover tracked originals, previews with recorded measurements and the text and whiteboard content you contributed. They are not a complete storage ledger."
        action={
          <Button icon="refresh" onClick={load}>
            Refresh usage
          </Button>
        }
      />
      {error && <ErrorState message={error} title="Usage could not be loaded" onRetry={() => void load()} />}
      {!data && !error && <Skeleton lines={5} label="Loading usage…" />}
      {data && (
        <Card title="Pilot upload counter">
          <div className="usage__body">
            <dl className="usage__list">
              <dt>Tracked original uploads</dt>
              <dd>
                {bytes(data.measurement.tracked_original_bytes)} · {data.measurement.tracked_files} files
              </dd>
              <dt>Pending original-byte reservations</dt>
              <dd>{bytes(data.measurement.pending_upload_original_bytes)}</dd>
              <dt>Previews with recorded measurements</dt>
              <dd>{bytes(data.measurement.tracked_preview_bytes ?? null)}</dd>
              <dt>Previews with unknown measurements</dt>
              <dd>{data.measurement.unknown_preview_files ?? "Unknown"}</dd>
              <dt>Uncommitted uploads</dt>
              <dd>{bytes(data.measurement.provisional_original_bytes)}</dd>
              <dt>Current pilot limit</dt>
              <dd>{bytes(data.runtime_limit.bytes)} (environment setting)</dd>
              <dt>Observed</dt>
              <dd>{fmtTime(data.measurement.observed_at)}</dd>
            </dl>
            <LogicalCharges charges={data.logical_charges} scope="user" />
            <p className="usage__note">
              Partial measurement: historical previews without expected measurements, other derivatives,
              non-upload reservations, trash and temporary archives are not fully measured here. Whiteboard
              history is shared site storage and is not charged to you. Preview metadata is not a current disk
              inspection. Your current pilot limit charges originals only; proposed policies do not change it.
            </p>
            <p>
              Archive downloads, quota exceptions and retention management are planned. Existing file
              downloads remain available on their posts. Contact your site administrator about the current
              pilot limit.
            </p>
          </div>
        </Card>
      )}
    </section>
  );
}
