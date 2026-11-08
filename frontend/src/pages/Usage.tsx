import { useEffect, useState } from 'react';
import { LogicalCharges } from '../components/LogicalCharges';
import type { UserUsage } from '../governance-types';
import { fmtBytes as bytes } from '../format';
import { api } from '../api';

export function Usage() {
  const [data, setData] = useState<UserUsage | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function load() {
    setError(null);
    try { setData(await api<UserUsage>('/usage')); }
    catch (e: any) { setError(e.message); }
  }
  useEffect(() => { load(); }, []);
  return <section>
    <h1>My storage usage</h1>
    <p>These counters cover tracked originals, previews with recorded measurements and the text and whiteboard content you contributed. They are not a complete storage ledger.</p>
    <button onClick={load}>Refresh usage</button>
    {error && <p className="error" role="alert">{error}</p>}
    {!data && !error && <p role="status">Loading usage…</p>}
    {data && <div className="card">
      <h2>Pilot upload counter</h2>
      <dl>
        <dt>Tracked original uploads</dt><dd>{bytes(data.measurement.tracked_original_bytes)} · {data.measurement.tracked_files} files</dd>
        <dt>Pending original-byte reservations</dt><dd>{bytes(data.measurement.pending_upload_original_bytes)}</dd>
        <dt>Previews with recorded measurements</dt><dd>{bytes(data.measurement.tracked_preview_bytes ?? null)}</dd>
        <dt>Previews with unknown measurements</dt><dd>{data.measurement.unknown_preview_files ?? 'Unknown'}</dd>
        <dt>Uncommitted uploads</dt><dd>{bytes(data.measurement.provisional_original_bytes)}</dd>
        <dt>Current pilot limit</dt><dd>{bytes(data.runtime_limit.bytes)} (environment setting)</dd>
        <dt>Observed</dt><dd>{new Date(data.measurement.observed_at).toLocaleString()}</dd>
      </dl>
      <LogicalCharges charges={data.logical_charges} scope="user" />
      <p className="notice">Partial measurement: historical previews without expected measurements, other derivatives, non-upload reservations, trash and temporary archives are not fully measured here. Whiteboard history is shared site storage and is not charged to you. Preview metadata is not a current disk inspection. Your current pilot limit charges originals only; proposed policies do not change it.</p>
      <p>Archive downloads, quota exceptions and retention management are planned. Existing file downloads remain available on their posts. Contact your site administrator about the current pilot limit.</p>
    </div>}
  </section>;
}
