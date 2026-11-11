import { useId, type ReactNode } from "react";
import "./display.css";

type CardProps = {
  title?: string;
  /** Heading level of the title, so cards sit correctly in the page outline. */
  level?: 2 | 3;
  actions?: ReactNode;
  children: ReactNode;
};

/** A bordered panel that groups related content, optionally with a title and actions. */
export function Card({ title, level = 2, actions, children }: CardProps) {
  const Heading = level === 2 ? "h2" : "h3";
  const headingId = useId();
  return (
    <section className="ui-card" aria-labelledby={title ? headingId : undefined}>
      {(title || actions) && (
        <header className="ui-card__header">
          {title && (
            <Heading className="ui-card__title" id={headingId}>
              {title}
            </Heading>
          )}
          {actions && <div className="ui-card__actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
