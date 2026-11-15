import React from "react";
import { CalendarEvent } from "./types";
import { fmtClockTimeIST } from "../../format";

type Props = {
  activeDate: Date;
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
  onCreateEventOnDate: (date: Date) => void;
};

export const MonthView: React.FC<Props> = ({ activeDate, events, onSelectEvent, onCreateEventOnDate }) => {
  const year = activeDate.getFullYear();
  const month = activeDate.getMonth();

  const firstDayOfWeek = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const cells: { date: Date; dayNum: number; isCurrentMonth: boolean }[] = [];

  // Prev month padding
  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const day = daysInPrevMonth - i;
    cells.push({
      date: new Date(year, month - 1, day),
      dayNum: day,
      isCurrentMonth: false,
    });
  }

  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({
      date: new Date(year, month, d),
      dayNum: d,
      isCurrentMonth: true,
    });
  }

  // Next month padding
  const remaining = (7 - (cells.length % 7)) % 7;
  for (let d = 1; d <= remaining; d++) {
    cells.push({
      date: new Date(year, month + 1, d),
      dayNum: d,
      isCurrentMonth: false,
    });
  }

  const today = new Date();
  const isSameDay = (d1: Date, d2: Date) =>
    d1.getFullYear() === d2.getFullYear() && d1.getMonth() === d2.getMonth() && d1.getDate() === d2.getDate();

  // Helper to check if event falls on a date
  const getEventsForDate = (cellDate: Date) => {
    const startOfDay = new Date(cellDate.getFullYear(), cellDate.getMonth(), cellDate.getDate(), 0, 0, 0);
    const endOfDay = new Date(cellDate.getFullYear(), cellDate.getMonth(), cellDate.getDate(), 23, 59, 59);

    return events.filter((ev) => {
      const evStart = new Date(ev.starts_at);
      const evEnd = new Date(ev.ends_at);
      return evStart <= endOfDay && evEnd >= startOfDay;
    });
  };

  const dayNames = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <div className="cal-month-header">
        {dayNames.map((name) => (
          <div key={name}>{name}</div>
        ))}
      </div>
      <div className="cal-month-grid">
        {cells.map((cell, idx) => {
          const isToday = isSameDay(cell.date, today);
          const cellEvents = getEventsForDate(cell.date);
          const maxVisible = 3;
          const visibleEvents = cellEvents.slice(0, maxVisible);
          const overflowCount = cellEvents.length - maxVisible;

          let cellClass = "cal-month-cell";
          if (!cell.isCurrentMonth) cellClass += " other-month";

          return (
            <div
              key={idx}
              className={cellClass}
              role="button"
              tabIndex={0}
              onClick={() => onCreateEventOnDate(cell.date)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onCreateEventOnDate(cell.date);
                }
              }}
            >
              <div className="cal-month-cell-header">
                <span className={`cal-month-daynum ${isToday ? "today" : ""}`}>{cell.dayNum}</span>
              </div>

              {visibleEvents.map((ev) => {
                const color = ev.color || "#1565c0";
                return (
                  <button
                    key={ev.id}
                    className="cal-event-chip"
                    style={{ backgroundColor: color }}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectEvent(ev);
                    }}
                    title={`${ev.title}${ev.location ? ` (${ev.location})` : ""}`}
                  >
                    {!ev.all_day && (
                      <span className="cal-event-chip-time">{fmtClockTimeIST(ev.starts_at)}</span>
                    )}
                    <span>{ev.title}</span>
                  </button>
                );
              })}

              {overflowCount > 0 && (
                <button
                  className="cal-event-chip-overflow"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCreateEventOnDate(cell.date);
                  }}
                >
                  +{overflowCount} more
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
