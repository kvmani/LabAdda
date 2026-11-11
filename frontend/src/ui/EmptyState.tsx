import type { ReactNode } from "react";
import "./display.css";

type EmptyStateProps = {
  title: string;
  /** What this place is for and how to fill it. */
  children?: ReactNode;
  action?: ReactNode;
};

/** Shown when a list or page has nothing yet; teaches the first step (UX-04, UX-08). */
export function EmptyState({ title, children, action }: EmptyStateProps) {
  return (
    <div className="ui-state">
      <p className="ui-state__title">{title}</p>
      {children && <div className="ui-state__body">{children}</div>}
      {action && <div className="ui-state__action">{action}</div>}
    </div>
  );
}
