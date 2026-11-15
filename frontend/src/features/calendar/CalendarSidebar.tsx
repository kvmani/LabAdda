import React, { useState } from "react";
import { CalendarSource } from "./types";

type Props = {
  sources: CalendarSource[];
  selectedSources: Set<string>;
  onToggleSource: (sourceId: string) => void;
  activeDate: Date;
  onSelectDate: (date: Date) => void;
  onCreateEvent: () => void;
};

export const CalendarSidebar: React.FC<Props> = ({
  sources,
  selectedSources,
  onToggleSource,
  activeDate,
  onSelectDate,
  onCreateEvent,
}) => {
  const [miniYear, setMiniYear] = useState(activeDate.getFullYear());
  const [miniMonth, setMiniMonth] = useState(activeDate.getMonth());

  const prevMiniMonth = () => {
    if (miniMonth === 0) {
      setMiniMonth(11);
      setMiniYear(miniYear - 1);
    } else {
      setMiniMonth(miniMonth - 1);
    }
  };

  const nextMiniMonth = () => {
    if (miniMonth === 11) {
      setMiniMonth(0);
      setMiniYear(miniYear + 1);
    } else {
      setMiniMonth(miniMonth + 1);
    }
  };

  // Generate days for mini month
  const firstDay = new Date(miniYear, miniMonth, 1).getDay();
  const daysInMonth = new Date(miniYear, miniMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(miniYear, miniMonth, 0).getDate();

  const miniDays: { dayNum: number; isCurrentMonth: boolean; date: Date }[] = [];

  // Prev month padding
  for (let i = firstDay - 1; i >= 0; i--) {
    const day = daysInPrevMonth - i;
    miniDays.push({
      dayNum: day,
      isCurrentMonth: false,
      date: new Date(miniYear, miniMonth - 1, day),
    });
  }

  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    miniDays.push({
      dayNum: d,
      isCurrentMonth: true,
      date: new Date(miniYear, miniMonth, d),
    });
  }

  // Next month padding to fill 35 or 42 cells
  const remaining = (7 - (miniDays.length % 7)) % 7;
  for (let d = 1; d <= remaining; d++) {
    miniDays.push({
      dayNum: d,
      isCurrentMonth: false,
      date: new Date(miniYear, miniMonth + 1, d),
    });
  }

  const today = new Date();
  const isSameDay = (d1: Date, d2: Date) =>
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate();

  const monthLabel = new Intl.DateTimeFormat("en-IN", {
    month: "long",
    year: "numeric",
  }).format(new Date(miniYear, miniMonth, 1));

  return (
    <aside className="cal-sidebar">
      <button className="cal-btn-create" onClick={onCreateEvent}>
        <span className="cal-btn-create-icon">+</span>
        <span>Create</span>
      </button>

      {/* Mini Calendar */}
      <div className="cal-mini-wrap">
        <div className="cal-mini-header">
          <span>{monthLabel}</span>
          <div>
            <button className="cal-nav-arrow" onClick={prevMiniMonth}>‹</button>
            <button className="cal-nav-arrow" onClick={nextMiniMonth}>›</button>
          </div>
        </div>
        <div className="cal-mini-grid">
          {["S", "M", "T", "W", "T", "F", "S"].map((name, i) => (
            <div key={i} className="cal-mini-dayname">{name}</div>
          ))}
          {miniDays.map((item, idx) => {
            const isToday = isSameDay(item.date, today);
            const isSelected = isSameDay(item.date, activeDate);
            let cls = "cal-mini-daycell";
            if (!item.isCurrentMonth) cls += " muted";
            if (isToday) cls += " today";
            if (isSelected) cls += " selected";

            return (
              <button
                key={idx}
                className={cls}
                onClick={() => onSelectDate(item.date)}
              >
                {item.dayNum}
              </button>
            );
          })}
        </div>
      </div>

      {/* My Calendars Filter */}
      <div className="cal-layers-section">
        <h4 className="cal-layers-title">My Calendars</h4>
        {sources.map((src) => {
          const checked = selectedSources.has(src.id);
          const badgeText = src.kind === "personal"
            ? "Private"
            : src.kind === "site"
            ? "Site"
            : src.level || src.kind;

          return (
            <label
              key={src.id}
              className="cal-layer-item"
              style={{ "--layer-color": src.color } as React.CSSProperties}
            >
              <input
                type="checkbox"
                className="cal-layer-checkbox"
                checked={checked}
                onChange={() => onToggleSource(src.id)}
              />
              <span
                className="cal-layer-dot"
                style={{ backgroundColor: src.color }}
              />
              <span className="cal-layer-label" title={src.title}>
                {src.title}
              </span>
              <span className="cal-layer-tag">{badgeText}</span>
            </label>
          );
        })}
      </div>
    </aside>
  );
};
