import type { ReactNode } from "react";
import "./display.css";

export type Tone = "neutral" | "info" | "ok" | "warn" | "danger";

/** A short label such as "Archived" or "Steward". The text carries the meaning, not the colour. */
export function Tag({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`ui-tag ui-tag--${tone}`}>{children}</span>;
}
