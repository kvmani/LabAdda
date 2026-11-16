import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api";
import { CalendarEvent, CalendarSource, CalendarViewMode, EventFormData } from "../features/calendar/types";
import { CalendarSidebar } from "../features/calendar/CalendarSidebar";
import { MonthView } from "../features/calendar/MonthView";
import { WeekDayView } from "../features/calendar/WeekDayView";
import { AgendaView } from "../features/calendar/AgendaView";
import { EventDialog } from "../features/calendar/EventDialog";
import "../features/calendar/calendar.css";

export const CalendarPage: React.FC = () => {
  const [activeDate, setActiveDate] = useState<Date>(new Date());
  const [viewMode, setViewMode] = useState<CalendarViewMode>("month");
  const [search, setSearch] = useState("");
  const [sources, setSources] = useState<CalendarSource[]>([]);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const generation = useRef(0);

  // Dialog state
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [createDate, setCreateDate] = useState<Date>(new Date());

  // 1. Load sources
  useEffect(() => {
    api<CalendarSource[]>("/calendar/sources")
      .then((data) => {
        setSources(data);
        setSelectedSources(new Set(data.map((s) => s.id)));
      })
      .catch((err: unknown) => setLoadError(errorMessage(err)));
  }, []);

  // 2. Compute date range for current view
  const computeRange = useCallback(() => {
    const year = activeDate.getFullYear();
    const month = activeDate.getMonth();

    if (viewMode === "month") {
      // 1 month before to 1 month after to cover full grid padding
      const start = new Date(year, month - 1, 1, 0, 0, 0);
      const end = new Date(year, month + 2, 0, 23, 59, 59);
      return { start: start.toISOString(), end: end.toISOString() };
    } else if (viewMode === "week") {
      const day = activeDate.getDay();
      const start = new Date(activeDate);
      start.setDate(activeDate.getDate() - day - 1);
      start.setHours(0, 0, 0, 0);
      const end = new Date(start);
      end.setDate(start.getDate() + 9);
      end.setHours(23, 59, 59, 999);
      return { start: start.toISOString(), end: end.toISOString() };
    } else if (viewMode === "day") {
      const start = new Date(activeDate);
      start.setHours(0, 0, 0, 0);
      const end = new Date(activeDate);
      end.setHours(23, 59, 59, 999);
      return { start: start.toISOString(), end: end.toISOString() };
    } else {
      // Agenda: from today/active date to 60 days ahead
      const start = new Date(activeDate);
      start.setHours(0, 0, 0, 0);
      const end = new Date(activeDate);
      end.setDate(activeDate.getDate() + 60);
      end.setHours(23, 59, 59, 999);
      return { start: start.toISOString(), end: end.toISOString() };
    }
  }, [activeDate, viewMode]);

  // 3. Load events
  const loadEvents = useCallback(() => {
    const token = ++generation.current;
    if (selectedSources.size === 0) {
      setEvents([]);
      setLoading(false);
      return;
    }
    const { start, end } = computeRange();
    const sourcesParam = Array.from(selectedSources).join(",");
    let url = `/calendar/events?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&sources=${encodeURIComponent(sourcesParam)}`;
    if (search.trim()) {
      url += `&search=${encodeURIComponent(search.trim())}`;
    }

    setLoading(true);
    setLoadError("");
    api<CalendarEvent[]>(url)
      .then((data) => {
        if (token === generation.current) setEvents(data);
      })
      .catch((err: unknown) => {
        if (token === generation.current) {
          setEvents([]);
          setLoadError(errorMessage(err));
        }
      })
      .finally(() => {
        if (token === generation.current) setLoading(false);
      });
  }, [computeRange, selectedSources, search]);

  useEffect(() => {
    loadEvents();
    return () => {
      generation.current += 1;
    };
  }, [loadEvents]);

  // Navigation handlers
  const handleToday = () => setActiveDate(new Date());

  const handlePrev = () => {
    const d = new Date(activeDate);
    if (viewMode === "month") d.setMonth(d.getMonth() - 1);
    else if (viewMode === "week") d.setDate(d.getDate() - 7);
    else if (viewMode === "day") d.setDate(d.getDate() - 1);
    else d.setDate(d.getDate() - 30);
    setActiveDate(d);
  };

  const handleNext = () => {
    const d = new Date(activeDate);
    if (viewMode === "month") d.setMonth(d.getMonth() + 1);
    else if (viewMode === "week") d.setDate(d.getDate() + 7);
    else if (viewMode === "day") d.setDate(d.getDate() + 1);
    else d.setDate(d.getDate() + 30);
    setActiveDate(d);
  };

  const handleToggleSource = (sourceId: string) => {
    const next = new Set(selectedSources);
    if (next.has(sourceId)) next.delete(sourceId);
    else next.add(sourceId);
    setSelectedSources(next);
  };

  // Header Title
  const getHeaderTitle = () => {
    if (viewMode === "month") {
      return new Intl.DateTimeFormat("en-IN", {
        month: "long",
        year: "numeric",
      }).format(activeDate);
    }
    if (viewMode === "day") {
      return new Intl.DateTimeFormat("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(activeDate);
    }
    return new Intl.DateTimeFormat("en-IN", {
      month: "short",
      year: "numeric",
    }).format(activeDate);
  };

  // Create / Edit / Delete Event Actions
  const handleOpenCreate = (date?: Date) => {
    setEditingEvent(null);
    setCreateDate(date || activeDate);
    setIsDialogOpen(true);
  };

  const handleOpenEdit = (ev: CalendarEvent) => {
    setEditingEvent(ev);
    setIsDialogOpen(true);
  };

  const handleSaveEvent = async (formData: EventFormData) => {
    const startsAt = new Date(`${formData.start_date}T${formData.start_time}:00`).toISOString();
    const endsAt = new Date(`${formData.end_date}T${formData.end_time}:00`).toISOString();

    if (formData.id) {
      // Patch
      await api(`/calendar/events/${formData.id}`, {
        method: "PATCH",
        body: {
          revision: formData.revision,
          title: formData.title,
          description: formData.description,
          location: formData.location,
          starts_at: startsAt,
          ends_at: endsAt,
          all_day: formData.all_day,
          color: formData.color,
        },
      });
    } else {
      // Create
      await api("/calendar/events", {
        method: "POST",
        body: {
          scope_kind: formData.scope_kind,
          workspace_id: formData.scope_kind === "workspace" ? formData.workspace_id : undefined,
          title: formData.title,
          description: formData.description,
          location: formData.location,
          starts_at: startsAt,
          ends_at: endsAt,
          all_day: formData.all_day,
          color: formData.color,
        },
      });
    }
    loadEvents();
  };

  const handleDeleteEvent = async (eventId: string) => {
    await api(`/calendar/events/${eventId}?revision=${editingEvent?.revision}`, { method: "DELETE" });
    loadEvents();
  };

  return (
    <div className="cal-container">
      {loadError && <p role="alert">{loadError}</p>}
      {/* Top Header Bar */}
      <header className="cal-topbar">
        <div className="cal-topbar-left">
          <div className="cal-title-section">
            <span className="cal-logo-icon">📅</span>
            <h2 className="cal-page-heading">Calendar</h2>
          </div>
          <div className="cal-nav-controls">
            <button className="cal-btn-today" onClick={handleToday}>
              Today
            </button>
            <button className="cal-nav-arrow" onClick={handlePrev} title="Previous">
              ‹
            </button>
            <button className="cal-nav-arrow" onClick={handleNext} title="Next">
              ›
            </button>
            <span className="cal-date-label">{getHeaderTitle()}</span>
            <span className="cal-timezone-badge">IST</span>
            {loading && <span style={{ fontSize: "0.75rem", color: "#1a73e8" }}>Syncing…</span>}
          </div>
        </div>

        <div className="cal-topbar-right">
          <input
            type="text"
            className="cal-search-input"
            placeholder="Search events..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="cal-view-selector">
            <button
              className={`cal-view-btn ${viewMode === "month" ? "active" : ""}`}
              onClick={() => setViewMode("month")}
            >
              Month
            </button>
            <button
              className={`cal-view-btn ${viewMode === "week" ? "active" : ""}`}
              onClick={() => setViewMode("week")}
            >
              Week
            </button>
            <button
              className={`cal-view-btn ${viewMode === "day" ? "active" : ""}`}
              onClick={() => setViewMode("day")}
            >
              Day
            </button>
            <button
              className={`cal-view-btn ${viewMode === "agenda" ? "active" : ""}`}
              onClick={() => setViewMode("agenda")}
            >
              Schedule
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="cal-body">
        <CalendarSidebar
          sources={sources}
          selectedSources={selectedSources}
          onToggleSource={handleToggleSource}
          activeDate={activeDate}
          onSelectDate={(d) => {
            setActiveDate(d);
            if (viewMode === "month") setViewMode("day");
          }}
          onCreateEvent={() => handleOpenCreate()}
        />

        <main className="cal-main">
          {viewMode === "month" && (
            <MonthView
              activeDate={activeDate}
              events={events}
              onSelectEvent={handleOpenEdit}
              onCreateEventOnDate={(d) => handleOpenCreate(d)}
            />
          )}

          {(viewMode === "week" || viewMode === "day") && (
            <WeekDayView
              activeDate={activeDate}
              mode={viewMode}
              events={events}
              onSelectEvent={handleOpenEdit}
              onCreateEventSlot={(d, hour) => {
                const target = new Date(d);
                target.setHours(hour, 0, 0, 0);
                handleOpenCreate(target);
              }}
            />
          )}

          {viewMode === "agenda" && <AgendaView events={events} onSelectEvent={handleOpenEdit} />}
        </main>
      </div>

      {/* Create / Edit Dialog */}
      <EventDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onSave={handleSaveEvent}
        onDelete={handleDeleteEvent}
        event={editingEvent}
        defaultDate={createDate}
        sources={sources}
      />
    </div>
  );
};
