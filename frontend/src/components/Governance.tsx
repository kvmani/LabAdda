import { useEffect, useRef, useState, type FormEvent } from 'react';
import { DatabaseStorage } from './DatabaseStorage';
import { LogicalCharges } from './LogicalCharges';
import { api } from '../api';
import { fmtBytes as bytes } from '../format';
import type { CapacityForecast as Forecast, CapacityProfile, PolicyDrafts, SiteUsage, Observation } from '../governance-types';
import { CapacityForecast } from './CapacityForecast';

const MiB = 1024 * 1024;
type StorageReceipt = {
  id: string; status: string; finished_at: string | null;
  summary: {
    checked_assets?: number; issue_count?: number; state?: string;
    verified_previews?: number; unknown_previews?: number;
    scope?: string; mode?: string; candidate_count?: number;
    applied_count?: number; stop_reason?: string;
    checked_items?: number; checked_boards?: number; correction_count?: number;
  };
};
const reconciliationStops: Record<string, string> = {
  plan_changed: 'Plan changed; the host operator must run a new dry run.',
  byte_budget_exhausted: 'Byte budget reached; reduce the batch size.',
  time_budget_exhausted: 'Time budget reached; reduce the batch size.',
  reconciliation_busy: 'Another reconciliation is running.',
  asset_root_unavailable: 'Asset storage is unavailable; check host storage.',
  board_object_budget_exhausted: 'Whiteboard object budget reached; reduce the batch size.',
};
export function Governance() {
  const [policy, setPolicy] = useState<PolicyDrafts | null>(null);
  const [usage, setUsage] = useState<SiteUsage | null>(null);
  const [inspections, setInspections] = useState<StorageReceipt[]>([]);
  const [history, setHistory] = useState<Observation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');
  const [fileLimit, setFileLimit] = useState(20);
  const [userLimit, setUserLimit] = useState(500);
  const [workspaceLimit, setWorkspaceLimit] = useState(2048);
  const [siteLimit, setSiteLimit] = useState('');
  const [reserve, setReserve] = useState(2048);
  const [reservePercent, setReservePercent] = useState(10);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const forecastGeneration = useRef(0);
  function invalidateForecast() { forecastGeneration.current++; setForecast(null); }
  function proposedProfile(): CapacityProfile {
    return {schema_version:2, mode:'observation', max_attachment_bytes:fileLimit*MiB,
      user_quota_bytes:userLimit*MiB, workspace_quota_bytes:workspaceLimit*MiB,
      site_asset_budget_bytes:siteLimit === '' ? null : Number(siteLimit)*MiB,
      filesystem_reserve_bytes:reserve*MiB, filesystem_reserve_percent:reservePercent};
  }
  async function preview() {
    const generation = ++forecastGeneration.current;
    setForecast(null); setError(null); setMessage(''); setBusy(true);
    try {
      const result = await api<Forecast>('/admin/capacity-forecasts', {body:{profile:proposedProfile()}});
      if (generation === forecastGeneration.current) setForecast(result);
    } catch(e: any) {
      if (generation === forecastGeneration.current) setError(e.fields?.map((f: {message:string})=>f.message).join('; ') || e.message);
    } finally { setBusy(false); }
  }
  async function load() {
    invalidateForecast();
    const [p, u, h, inspections] = await Promise.all([api<PolicyDrafts>('/admin/policy-drafts'), api<SiteUsage>('/admin/usage'), api<{observations: Observation[]}>('/admin/usage-observations'), api('/admin/storage-inspections')]);
    setPolicy(p); setUsage(u); setHistory(h.observations); setInspections(inspections.inspections);
  }
  useEffect(() => { load().catch(e => setError(e.message)); }, []);
  async function run(action: () => Promise<any>, success: string) {
    setBusy(true); setError(null); setMessage('');
    try { await action(); await load(); setMessage(success); }
    catch (e: any) { setError(e.fields?.length ? e.fields.map((f: {field: string; message: string}) => `${f.field}: ${f.message}`).join("; ") : e.message); }
    finally { setBusy(false); }
  }
  async function propose(e: FormEvent) {
    e.preventDefault();
    invalidateForecast();
    await run(() => api('/admin/policy-drafts', { body: {
      base_revision: policy!.latest_revision, reason,
      profile: proposedProfile()
    }}), 'Proposal saved. No limits or retention rules were activated.');
  }
  return <div className="card">
    <h2>Storage observations and policy proposals</h2>
    <p>Foundation preview: saving proposals cannot activate enforcement or delete data. Current pilot limits remain environment-controlled.</p>
    {error && <p className="error" role="alert">{error} Reload observations before retrying a conflicted proposal.</p>}
    {message && <p role="status">{message}</p>}
    <button disabled={busy} onClick={() => run(async () => {}, 'Observations refreshed.')}>Reload observations</button>
    {!policy && !error && <p role="status">Loading governance information…</p>}
    {usage && <>
      <h3>Site measurements (partial)</h3>
      <dl>
        <dt>Tracked original file bytes</dt><dd>{bytes(usage.assets.tracked_original_bytes)} · {usage.assets.tracked_files} files</dd>
        <dt>Pending original-byte reservations</dt><dd>{bytes(usage.assets.pending_upload_original_bytes)}</dd>
        <dt>Previews with recorded measurements</dt><dd>{bytes(usage.assets.tracked_preview_bytes ?? null)}</dd>
        <dt>Previews with unknown measurements</dt><dd>{usage.assets.unknown_preview_files ?? 'Unknown'}</dd>
        <dt>Asset filesystem free space</dt><dd>{bytes(usage.filesystem.free_bytes)} · {usage.filesystem.state}</dd>
        <dt>Configured site budget</dt><dd>Not configured</dd>
        <dt>Observed</dt><dd>{new Date(usage.assets.observed_at).toLocaleString()}</dd>
      </dl>
      <LogicalCharges charges={usage.logical_charges} scope="site" />
      <DatabaseStorage storage={usage.database} />
      <p className="notice">Filesystem capacity may be shared with other services. Historical previews without expected measurements, other derivatives, non-upload reservations, trash and archive storage are not fully measured. Preview metadata is not a current disk inspection. These totals cannot approve enforcement or deletion.</p>
      <button disabled={busy} onClick={() => run(() => api('/admin/usage-observations', {body: {}}), 'Partial observation recorded.')}>Record partial observation</button>
      <p>{Math.min(history.length, 5)} recent samples displayed; at most 100 operational samples retained.</p>
      {history.length > 0 && <ul>{history.slice(0, 5).map(h => <li key={h.id}>{new Date(h.observed_at).toLocaleString()} · {bytes(h.measurement.assets.tracked_original_bytes)} tracked originals</li>)}</ul>}
    </>}
    <h3>Referenced file inspections and reconciliations</h3>
    <p>Run by the host operator with <code>labadda inspect-storage</code>. Inspections verify original hashes and preview hashes where expected measurements exist. Historical preview integrity remains unknown without those measurements. The scan time budget is cooperative, not a hard filesystem timeout. Inspections never repair files or authorize enforcement. A running record may be stale after an operator process stops.</p>
    {inspections.length === 0 ? <p>No inspection receipts available.</p> : <ul>{inspections.map(r => <li key={r.id}>{r.status}{r.summary.scope === 'content_charge_reconciliation' ? '' : ` · ${r.summary.checked_assets ?? 'Not reported'} asset rows checked`} · {r.summary.issue_count ?? 'Not reported'} issues · {r.finished_at ? new Date(r.finished_at).toLocaleString() : 'No completion receipt'}
      {r.summary.scope === 'content_charge_reconciliation'
        ? <span className="muted small"> · Text/whiteboard charge reconciliation {r.summary.mode === 'dry_run' ? 'Dry run' : r.summary.mode === 'apply' ? 'Apply' : 'Unknown mode'}: {r.summary.checked_items ?? 'Not reported'} text items · {r.summary.checked_boards ?? 'Not reported'} boards · {r.summary.correction_count ?? 'Not reported'} ledger corrections planned · {r.summary.applied_count ?? 'Unconfirmed'} applied{r.summary.stop_reason && ` · ${reconciliationStops[r.summary.stop_reason] ?? 'Host operator inspection required.'}`}</span>
        : r.summary.scope === 'preview_metadata_reconciliation'
        ? <span className="muted small"> · Preview reconciliation {r.summary.mode === 'dry_run' ? 'Dry run' : r.summary.mode === 'apply' ? 'Apply' : 'Unknown mode'}: {r.summary.candidate_count ?? 'Not reported'} candidates · {r.summary.applied_count ?? 'Unconfirmed'} metadata updates{r.summary.stop_reason && ` · ${reconciliationStops[r.summary.stop_reason] ?? 'Host operator inspection required.'}`}</span>
        : <span className="muted small"> · Preview checks: {r.summary.verified_previews ?? 'Not reported'} verified · {r.summary.unknown_previews ?? 'Not reported'} unknown expected measurements</span>}
    </li>)}</ul>}
    {policy && <>
      <h3>Site proposal revision {policy.latest_revision}</h3>
      <p>Current pilot file limit: {bytes(policy.runtime_limits.max_attachment_bytes)}. Current pilot user limit: {bytes(policy.runtime_limits.user_quota_bytes)}.</p>
      <form onSubmit={propose} className="governance-form">
        <label>Proposed file limit (MiB)<input type="number" min="1" max="100" step="1" required value={fileLimit} onChange={e => {invalidateForecast(); setFileLimit(Number(e.target.value));}} /></label>
        <label>Proposed user limit (MiB)<input type="number" min="1" max="102400" step="1" required value={userLimit} onChange={e => {invalidateForecast(); setUserLimit(Number(e.target.value));}} /></label>
        <label>Proposed workspace limit (MiB)<input type="number" min="1" max="1024000" step="1" required value={workspaceLimit} onChange={e => {invalidateForecast(); setWorkspaceLimit(Number(e.target.value));}} /></label>
        <label>Proposed site asset budget (MiB; blank means not configured)<input type="number" min="1" max="10485760" step="1" value={siteLimit} onChange={e => {invalidateForecast(); setSiteLimit(e.target.value);}} /></label>
        <label>Proposed filesystem reserve floor (MiB)<input type="number" min="1" max="102400" step="1" required value={reserve} onChange={e => {invalidateForecast(); setReserve(Number(e.target.value));}} /></label>
        <label>Proposed filesystem reserve (%)<input type="number" min="1" max="50" step="1" required value={reservePercent} onChange={e => {invalidateForecast(); setReservePercent(Number(e.target.value));}} /></label>
        <p>The proposed reserve is the greater of its floor and percentage of observed filesystem capacity. Preview estimates use originals, recorded previews and pending originals; other storage remains unmeasured.</p>
        <button type="button" disabled={busy} onClick={preview}>Preview proposed capacity</button>
        {forecast && <CapacityForecast forecast={forecast} />}
        <label>Proposal reason<textarea required minLength={3} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <button disabled={busy}>Save non-enforcing proposal</button>
      </form>
      <div className="table-scroll" role="region" aria-label="Policy proposal history" tabIndex={0}><table><caption>Recent immutable proposals</caption><thead><tr><th>Revision</th><th>Proposed file / user / workspace limits</th><th>Proposed site assets / reserve</th><th>Reason</th><th>Status</th></tr></thead>
        <tbody>{policy.drafts.map((d) => <tr key={d.id}><td>{d.revision}</td><td>{bytes(d.profile.max_attachment_bytes)} / {bytes(d.profile.user_quota_bytes)} / {bytes(d.profile.workspace_quota_bytes)}</td><td>{d.profile.schema_version === 2 ? <>{d.profile.site_asset_budget_bytes === null ? 'Not configured' : bytes(d.profile.site_asset_budget_bytes ?? null)} / {bytes(d.profile.filesystem_reserve_bytes ?? null)} or {d.profile.filesystem_reserve_percent}% (greater)</> : 'Not recorded in version 1'}</td><td>{d.reason}</td><td>Draft only</td></tr>)}</tbody></table></div>
    </>}
  </div>;
}
