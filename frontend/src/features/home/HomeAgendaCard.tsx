import { Link } from "react-router-dom";
import { Skeleton } from "../../ui";
import { fmtTime } from "../../format";
import type { CalendarEvent } from "../calendar/types";
type Props = {
  todayEvents: CalendarEvent[];
  eventsError: string;
  eventsLoading: boolean;
  todayFormatted: string;
  timezone: string;
};
function formatEventTime(start: string, end: string, timezone: string) {
  return `${fmtTime(start, timezone)} – ${fmtTime(end, timezone)}`;
}
export function HomeAgendaCard({ todayEvents, eventsError, eventsLoading, todayFormatted, timezone }: Props) {
  return (
    <section className="wb-card" aria-label="Today's schedule">
      <div className="wb-card__header">
        <div>
          <h2 className="wb-card__title">
            <span className="wb-card__icon" aria-hidden="true">
              🗓️
            </span>
            <span>Today’s Schedule</span>
          </h2>
          <p className="wb-card__subtitle">Seminars, meetings and deadlines for {todayFormatted}</p>
        </div>
        <Link to="/calendar" className="wb-card__link">
          Open Calendar →
        </Link>
      </div>

      <div className="wb-card__body">
        {eventsError ? (
          <p role="alert">{eventsError}</p>
        ) : eventsLoading ? (
          <Skeleton label="Loading today's schedule" />
        ) : todayEvents.length === 0 ? (
          <div className="wb-empty">
            <p className="wb-empty__text">No events or meetings scheduled for today.</p>
            <Link to="/calendar" className="ui-button ui-button--secondary ui-button--sm">
              + Schedule an event
            </Link>
          </div>
        ) : (
          <ul className="wb-event-list">
            {todayEvents.map((ev) => (
              <li key={ev.id} className="wb-event-item">
                <div className="wb-event-item__time-box">
                  <span className="wb-event-item__time">
                    {ev.all_day ? "All Day" : formatEventTime(ev.starts_at, ev.ends_at, timezone)}
                  </span>
                </div>
                <div className="wb-event-item__details">
                  <h3 className="wb-event-item__title">{ev.title}</h3>
                  <p className="wb-event-item__meta">
                    {ev.location && (
                      <span className="wb-event-item__loc">
                        📍 {ev.location}
                        <span className="wb-hero__separator" aria-hidden="true">
                          ·
                        </span>
                      </span>
                    )}
                    <span className="wb-badge wb-badge--scope">
                      {ev.scope_kind === "site"
                        ? "Site-wide"
                        : ev.scope_kind === "personal"
                          ? "My calendar"
                          : ev.workspace_name || "Workspace"}
                    </span>
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
