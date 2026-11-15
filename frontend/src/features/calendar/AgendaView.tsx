import React from "react";
import { CalendarEvent } from "./types";
import { fmtClockTimeIST, fmtDateBadgeIST } from "../../format";

type Props = {
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
};

export const AgendaView: React.FC<Props> = ({ events, onSelectEvent }) => {
  if (events.length === 0) {
    return (
      <div style={{ padding: 48, textAlign: "center", color: "var(--text-muted, #6b7280)" }}>
        <p style={{ fontSize: "1.1rem", fontWeight: 500 }}>No upcoming events scheduled</p>
        <p style={{ fontSize: "0.875rem" }}>
          Click "Create" in the sidebar to schedule your first meeting or activity.
        </p>
      </div>
    );
  }

  // Group events by date key YYYY-MM-DD
  const groups: { [dateKey: string]: CalendarEvent[] } = {};
  for (const ev of events) {
    const d = new Date(ev.starts_at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(ev);
  }

  const sortedEntries = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="cal-agenda-container">
      {sortedEntries.map(([dateKey, dayEvents]) => {
        const firstEvent = dayEvents[0];
        if (!firstEvent) return null;
        const dateHeader = fmtDateBadgeIST(firstEvent.starts_at);
        const fullDateStr = new Intl.DateTimeFormat("en-IN", {
          weekday: "long",
          day: "numeric",
          month: "long",
          year: "numeric",
        }).format(new Date(firstEvent.starts_at));

        return (
          <div key={dateKey} className="cal-agenda-group">
            <div className="cal-agenda-date-header">
              <span>{fullDateStr}</span>
              <span className="cal-timezone-badge">{dateHeader}</span>
            </div>
            {dayEvents.map((ev) => {
              const color = ev.color || "#1565c0";
              const timeStr = ev.all_day
                ? "All day"
                : `${fmtClockTimeIST(ev.starts_at)} - ${fmtClockTimeIST(ev.ends_at)}`;

              return (
                <button
                  type="button"
                  key={ev.id}
                  className="cal-agenda-item"
                  onClick={() => onSelectEvent(ev)}
                >
                  <div className="cal-agenda-time">{timeStr}</div>
                  <div className="cal-agenda-color-pill" style={{ backgroundColor: color }} />
                  <div className="cal-agenda-details">
                    <span className="cal-agenda-item-title">{ev.title}</span>
                    <div className="cal-agenda-meta">
                      {ev.workspace_name && <span>🏢 {ev.workspace_name}</span>}
                      {ev.scope_kind === "site" && <span>🌐 Institute-wide</span>}
                      {ev.scope_kind === "personal" && <span>🔒 Private</span>}
                      {ev.location && <span>📍 {ev.location}</span>}
                      {ev.creator_name && <span>👤 {ev.creator_name}</span>}
                    </div>
                    {ev.description && (
                      <p style={{ margin: "4px 0 0", fontSize: "0.85rem", color: "var(--text, #4b5563)" }}>
                        {ev.description}
                      </p>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};
