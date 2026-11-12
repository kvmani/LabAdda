import { Link } from "react-router-dom";
import { EmptyState, StatusPill } from "../../ui";
import type { IconName } from "../../ui";
import { SEVERITY_LABEL } from "./model";
import type { AttentionEntry, Severity } from "./types";

const ICON: Record<Severity, IconName> = {
  critical: "error",
  error: "error",
  warning: "warning",
  info: "help",
};
const TONE = { critical: "danger", error: "danger", warning: "warn", info: "neutral" } as const;

function Entry({ entry }: { entry: AttentionEntry }) {
  return (
    <li className="overview-entry">
      <div className="overview-entry__head">
        {entry.status ? (
          <StatusPill status={entry.status} />
        ) : (
          <StatusPill
            tone={TONE[entry.severity]}
            icon={ICON[entry.severity]}
            label={SEVERITY_LABEL[entry.severity]}
          />
        )}
        <p className="overview-entry__title">{entry.title}</p>
      </div>
      <p className="overview-entry__detail">{entry.detail}</p>
      <p className="overview-entry__links">
        <Link to={entry.route}>Open {entry.title}</Link>
        {entry.help && (
          <Link to={`/help/${entry.help}`} aria-label={`What to do: ${entry.title}`}>
            What to do
          </Link>
        )}
      </p>
    </li>
  );
}

/** What needs a person, most serious first; says so plainly when nothing does (UX-10). */
export function Attention({ entries, healthy }: { entries: AttentionEntry[]; healthy: boolean }) {
  if (entries.length === 0)
    return (
      <EmptyState
        title={healthy ? "Nothing needs attention" : "No problems found, but not everything is confirmed"}
      >
        {healthy
          ? "Every check is healthy, no event is waiting, and every unit has someone in charge."
          : "Some checks have no figures yet. Open System health to see which."}
      </EmptyState>
    );
  return (
    <ol className="overview-attention" aria-label="Needs attention, most serious first">
      {entries.map((entry) => (
        <Entry key={entry.id} entry={entry} />
      ))}
    </ol>
  );
}
