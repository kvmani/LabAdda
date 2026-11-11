import { Icon } from "../Icon";
import type { IconName } from "../icons";
import { defaultValueFormat } from "./format";
import "./charts.css";

type MeterProps = {
  /** What is measured, for example "Disk space". */
  label: string;
  /** Null when it could not be measured; shown as not measured, never as zero. */
  value: number | null;
  /** The limit the value is measured against. */
  max: number;
  unit?: string;
  /** Value at which the meter turns to a warning. */
  warnAt?: number;
  /** Value at which the meter turns to danger. */
  dangerAt?: number;
  formatValue?: (value: number) => string;
};

type Level = "ok" | "warn" | "danger" | "unknown";
const LEVELS: Record<Level, { word: string; icon: IconName }> = {
  ok: { word: "Within limits", icon: "success" },
  warn: { word: "Getting full", icon: "warning" },
  danger: { word: "At or near the limit", icon: "error" },
  unknown: { word: "Not measured", icon: "info" },
};

function levelOf(value: number | null, warnAt?: number, dangerAt?: number): Level {
  if (value === null) return "unknown";
  if (dangerAt !== undefined && value >= dangerAt) return "danger";
  if (warnAt !== undefined && value >= warnAt) return "warn";
  return "ok";
}

/** One value against a limit, with warn and danger thresholds shown in words as well as colour. */
export function Meter({
  label,
  value,
  max,
  unit,
  warnAt,
  dangerAt,
  formatValue = defaultValueFormat,
}: MeterProps) {
  const level = levelOf(value, warnAt, dangerAt);
  const share = value === null || max <= 0 ? 0 : Math.min(1, Math.max(0, value / max));
  const withUnit = (n: number) => (unit ? `${formatValue(n)} ${unit}` : formatValue(n));
  const text =
    value === null ? "Not measured" : `${withUnit(value)} of ${withUnit(max)} (${Math.round(share * 100)}%)`;
  const { word, icon } = LEVELS[level];
  return (
    <div className={`ui-meter ui-meter--${level}`}>
      <div className="ui-meter__head">
        <span className="ui-meter__label">{label}</span>
        <span className="ui-meter__status">
          <Icon name={icon} size="sm" />
          {word}
        </span>
      </div>
      <div
        className="ui-meter__track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value ?? undefined}
        aria-valuetext={`${text}. ${word}.`}
      >
        <svg viewBox="0 0 100 1" preserveAspectRatio="none" aria-hidden="true" focusable="false">
          <rect className="ui-meter__fill" x={0} y={0} width={share * 100} height={1} />
          {[warnAt, dangerAt].map((mark, index) =>
            mark === undefined || max <= 0 ? null : (
              <line
                key={index}
                className="ui-meter__mark"
                x1={(mark / max) * 100}
                x2={(mark / max) * 100}
                y1={0}
                y2={1}
              />
            ),
          )}
        </svg>
      </div>
      <p className="ui-meter__text">{text}</p>
    </div>
  );
}
