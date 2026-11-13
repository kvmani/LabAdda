import { useEffect, useState } from "react";
import { Button, Icon } from "../../ui";
import type { SiteMessage } from "./types";
import "./broadcast.css";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia?.(REDUCED_MOTION).matches ?? false);
  useEffect(() => {
    const query = window.matchMedia?.(REDUCED_MOTION);
    if (!query) return;
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

function speed(messages: SiteMessage[]): 1 | 2 | 3 {
  const length = messages.reduce((sum, item) => sum + item.message.length, 0);
  return length <= 150 ? 1 : length <= 400 ? 2 : 3;
}

/**
 * Scrolling site announcements (WCAG 2.2.2): a visible Pause/Play button, paused while hovered or
 * holding keyboard focus, and listed still when the person prefers reduced motion. The moving copy is
 * hidden from screen readers; one polite status region carries the text and changes only with it.
 */
export function BroadcastStrip({ messages }: { messages: SiteMessage[] }) {
  const reduced = useReducedMotion();
  const [paused, setPaused] = useState(false);
  if (messages.length === 0) return null;
  const warning = messages.some((item) => item.level === "warning");
  const spoken = messages
    .map((item) => `${item.level === "warning" ? "Warning" : "Notice"}: ${item.message}`)
    .join(" ");
  const classes = [
    "broadcast-strip",
    `broadcast-strip--${warning ? "warning" : "info"}`,
    reduced ? "broadcast-strip--still" : paused ? "broadcast-strip--paused" : "",
  ];
  return (
    <section
      className={classes.filter(Boolean).join(" ")}
      aria-label="Announcements"
      data-testid="broadcast-strip"
    >
      <div className="broadcast-strip__window" aria-hidden="true">
        <ul className={`broadcast-strip__track broadcast-strip__track--speed-${speed(messages)}`}>
          {messages.map((item) => (
            <li key={item.id} className="broadcast-strip__item">
              <Icon name={item.level === "warning" ? "warning" : "info"} size="sm" />
              <strong>{item.level === "warning" ? "Warning:" : "Notice:"}</strong>
              <span>{item.message}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="ui-visually-hidden" role="status" aria-live="polite">
        {spoken}
      </div>
      {!reduced && (
        <Button size="sm" variant="secondary" aria-pressed={paused} onClick={() => setPaused((now) => !now)}>
          {paused ? "Play announcements" : "Pause announcements"}
        </Button>
      )}
    </section>
  );
}
