import "./base.css";
import "./display.css";

type SkeletonProps = {
  /** Number of placeholder lines shaped like the content that is loading. */
  lines?: number;
  /** Announced to screen readers, for example "Loading people…". */
  label?: string;
};

/** Grey placeholder lines while content loads, so the layout does not jump (UX-04). */
export function Skeleton({ lines = 3, label = "Loading…" }: SkeletonProps) {
  return (
    <div className="ui-skeleton" role="status" aria-live="polite">
      <span className="ui-visually-hidden">{label}</span>
      {Array.from({ length: lines }, (_, index) => (
        <span key={index} className="ui-skeleton__line" aria-hidden="true" />
      ))}
    </div>
  );
}
