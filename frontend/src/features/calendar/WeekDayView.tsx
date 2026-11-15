import React from "react";
import { CalendarEvent } from "./types";
import { fmtClockTimeIST } from "../../format";

type Props = {
  activeDate: Date;
  mode: "week" | "day";
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
  onCreateEventSlot: (date: Date, hour: number) => void;
};

export const WeekDayView: React.FC<Props> = ({
  activeDate,
  mode,
  events,
  onSelectEvent,
  onCreateEventSlot,
}) => {
  const days: Date[] = [];
  if (mode === "day") {
    days.push(new Date(activeDate));
  } else {
    // Week: start from Sunday or Monday
    const currentDayOfWeek = activeDate.getDay();
    const startOfWeek = new Date(activeDate);
    startOfWeek.setDate(activeDate.getDate() - currentDayOfWeek);

    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek);
      d.setDate(startOfWeek.getDate() + i);
      days.push(d);
    }
  }

  const hours = Array.from({ length: 24 }, (_, i) => i);

  const isSameDay = (d1: Date, d2: Date) =>
    d1.getFullYear() === d2.getFullYear() && d1.getMonth() === d2.getMonth() && d1.getDate() === d2.getDate();

  const today = new Date();

  const scrollRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 430;
    }
  }, [mode, activeDate]);

  // All day events on these days
  const allDayEvents = events.filter((ev) => ev.all_day);

  // Time slotted events
  const timedEvents = events.filter((ev) => !ev.all_day);

  return (
    <div className="cal-time-grid-container">
      {/* Week/Day Header */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border, #e5e7eb)",
          background: "var(--surface, #fafafa)",
        }}
      >
        <div style={{ width: 60, flexShrink: 0, borderRight: "1px solid var(--border, #e5e7eb)" }} />
        <div style={{ display: "flex", flex: 1 }}>
          {days.map((day, idx) => {
            const isToday = isSameDay(day, today);
            const dayName = new Intl.DateTimeFormat("en-IN", { weekday: "short" }).format(day).toUpperCase();
            return (
              <div
                key={idx}
                style={{
                  flex: 1,
                  textAlign: "center",
                  padding: "8px 0",
                  borderRight: "1px solid var(--border, #e5e7eb)",
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted, #6b7280)", fontWeight: 600 }}>
                  {dayName}
                </div>
                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    fontSize: "0.95rem",
                    fontWeight: isToday ? 700 : 500,
                    background: isToday ? "#1a73e8" : "transparent",
                    color: isToday ? "#ffffff" : "inherit",
                  }}
                >
                  {day.getDate()}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* All-Day Bar */}
      {allDayEvents.length > 0 && (
        <div className="cal-time-all-day-bar">
          <div className="cal-time-all-day-label">All day</div>
          <div className="cal-time-all-day-content">
            {allDayEvents.map((ev) => (
              <button
                key={ev.id}
                className="cal-event-chip"
                style={{ backgroundColor: ev.color || "#1565c0" }}
                onClick={() => onSelectEvent(ev)}
              >
                {ev.title}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Hourly Scroll Area */}
      <div className="cal-time-body" ref={scrollRef}>
        {/* Time axis */}
        <div className="cal-time-axis">
          {hours.map((h) => {
            const label = h === 0 ? "12 AM" : h < 12 ? `${h} AM` : h === 12 ? "12 PM" : `${h - 12} PM`;
            return (
              <div key={h} className="cal-time-axis-slot">
                {label}
              </div>
            );
          })}
        </div>

        {/* Columns for each day */}
        <div className="cal-time-columns">
          {days.map((day, colIdx) => {
            // Events for this specific day
            const dayTimed = timedEvents.filter((ev) => {
              const evDate = new Date(ev.starts_at);
              return isSameDay(evDate, day);
            });

            return (
              <div key={colIdx} className="cal-time-col">
                {hours.map((h) => (
                  <button
                    type="button"
                    key={h}
                    className="cal-time-col-slot"
                    aria-label={`Slot at ${h}:00`}
                    onClick={() => onCreateEventSlot(day, h)}
                  />
                ))}

                {/* Render Event Blocks */}
                {dayTimed.map((ev) => {
                  const evStart = new Date(ev.starts_at);
                  const evEnd = new Date(ev.ends_at);
                  const startHour = evStart.getHours() + evStart.getMinutes() / 60;
                  const endHour = evEnd.getHours() + evEnd.getMinutes() / 60;
                  const duration = Math.max(0.5, endHour - startHour);

                  const top = startHour * 48;
                  const height = duration * 48 - 4;
                  const color = ev.color || "#1565c0";

                  return (
                    <button
                      type="button"
                      key={ev.id}
                      className="cal-time-event-block"
                      style={{
                        top: `${top}px`,
                        height: `${height}px`,
                        backgroundColor: color,
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectEvent(ev);
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>{ev.title}</div>
                      <div style={{ fontSize: "0.75rem", opacity: 0.9 }}>
                        {fmtClockTimeIST(ev.starts_at)} - {fmtClockTimeIST(ev.ends_at)}
                      </div>
                      {ev.location && (
                        <div style={{ fontSize: "0.75rem", opacity: 0.85 }}>📍 {ev.location}</div>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
