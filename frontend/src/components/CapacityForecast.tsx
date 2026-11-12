import type { CapacityForecast as Forecast } from "../governance-types";
import { fmtBytes } from "../format";
import "./storage.css";

const warnings: Record<string, string> = {
  unmeasured_storage_classes:
    "Some stored files, temporary data and system overhead are not attributed by these counters.",
  site_budget_unconfigured: "No proposed site asset budget is configured.",
  known_lower_bound_over_budget:
    "Known originals, previews and pending originals already exceed the proposed site asset budget.",
  unknown_preview_measurements: "Historical previews with unknown sizes can consume additional space.",
  filesystem_unavailable: "Filesystem capacity is unavailable. Ask the host operator to inspect storage.",
  reserve_exceeds_filesystem:
    "The proposed reserve exceeds the observed filesystem size. Review the proposal.",
  filesystem_reserve_not_met:
    "Observed free space is below the proposed reserve. Review capacity with the host operator.",
};

export function CapacityForecast({ forecast }: { forecast: Forecast }) {
  return (
    <section className="storage-note storage-section" aria-label="Capacity preview">
      <h4 className="storage-subheading">Capacity preview (incomplete)</h4>
      <dl className="storage-list">
        <dt>Known assets and pending originals (lower bound)</dt>
        <dd>{fmtBytes(forecast.known_asset_lower_bound_bytes)}</dd>
        <dt>Maximum possible headroom under proposed asset budget</dt>
        <dd>
          {forecast.site_asset_budget.proposed_bytes === null
            ? "Not configured"
            : fmtBytes(forecast.site_asset_budget.maximum_possible_headroom_bytes)}
        </dd>
        <dt>Proposed reserve on observed filesystem</dt>
        <dd>{fmtBytes(forecast.filesystem.proposed_reserve_bytes)}</dd>
        <dt>Maximum growth above proposed filesystem reserve</dt>
        <dd>{fmtBytes(forecast.filesystem.maximum_growth_above_reserve_bytes)}</dd>
        <dt>Shortfall below proposed filesystem reserve</dt>
        <dd>{fmtBytes(forecast.filesystem.reserve_shortfall_bytes)}</dd>
        <dt>Asset counters observed</dt>
        <dd>{new Date(forecast.asset_observed_at).toLocaleString()}</dd>
        <dt>Filesystem observed independently</dt>
        <dd>
          {new Date(forecast.filesystem.observed_at).toLocaleString()} · {forecast.filesystem.state}
        </dd>
      </dl>
      <ul className="storage-steps">
        {forecast.warnings.map((code) => (
          <li key={code}>
            {warnings[code] ?? "Capacity observation is incomplete; ask the host operator to inspect."}
          </li>
        ))}
      </ul>
      <p>
        Headroom is an upper bound, not guaranteed available space. Filesystem capacity can be shared with
        other services. This preview cannot approve enforcement, reserve storage or change a limit.
      </p>
    </section>
  );
}
