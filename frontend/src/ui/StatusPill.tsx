import { Icon } from "./Icon";
import type { IconName } from "./icons";
import type { Tone } from "./Tag";
import "./display.css";

/** The six health words every dashboard uses (AD-03). Missing data is never shown as healthy. */
export type HealthStatus = "healthy" | "degraded" | "unavailable" | "stale" | "unknown" | "unsupported";

const HEALTH: Record<HealthStatus, { tone: Tone; icon: IconName; word: string }> = {
  healthy: { tone: "ok", icon: "success", word: "Healthy" },
  degraded: { tone: "warn", icon: "warning", word: "Degraded" },
  unavailable: { tone: "danger", icon: "error", word: "Unavailable" },
  stale: { tone: "warn", icon: "clock", word: "Stale" },
  unknown: { tone: "neutral", icon: "help", word: "Unknown" },
  unsupported: { tone: "neutral", icon: "minus", word: "Not supported" },
};

type StatusPillProps =
  { status: HealthStatus } | { tone: Tone; icon: IconName; label: string; status?: never };

/** A status shown as icon plus word, for health and for person or unit states. */
export function StatusPill(props: StatusPillProps) {
  const { tone, icon, word } =
    props.status !== undefined
      ? HEALTH[props.status]
      : { tone: props.tone, icon: props.icon, word: props.label };
  return (
    <span className={`ui-pill ui-tag--${tone}`}>
      <Icon name={icon} size="sm" />
      <span>{word}</span>
    </span>
  );
}
