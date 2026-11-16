import React, { useState, useRef } from "react";
import { useFocusTrap } from "../../ui/focus";
import type { CalendarEvent, CalendarScopeKind, CalendarSource, EventFormData } from "./types";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (eventData: EventFormData) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  event?: CalendarEvent | null;
  defaultDate?: Date;
  sources: CalendarSource[];
};

const PALETTE = [
  "#1565c0", // Royal Blue
  "#2e7d32", // Forest Green
  "#d81b60", // Rose
  "#e65100", // Dark Amber
  "#00838f", // Deep Cyan
  "#6a1b9a", // Deep Purple
  "#c62828", // Crimson
  "#455a64", // Slate
];

export const EventDialog: React.FC<Props> = (props) => {
  if (!props.isOpen) return null;
  return <EventForm {...props} />;
};

function EventForm({ onClose, onSave, onDelete, event, defaultDate, sources }: Props) {
  const formatDateYMD = (d: Date) => {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const formatTimeHM = (d: Date) => {
    const hours = String(d.getHours()).padStart(2, "0");
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${hours}:${minutes}`;
  };

  const initStartDate = event ? new Date(event.starts_at) : defaultDate || new Date();
  const initEndDate = event ? new Date(event.ends_at) : new Date(initStartDate.getTime() + 60 * 60 * 1000);

  const [title, setTitle] = useState(event ? event.title : "");
  const [description, setDescription] = useState(event?.description || "");
  const [location, setLocation] = useState(event?.location || "");
  const [allDay, setAllDay] = useState(event ? event.all_day : false);
  const [startDate, setStartDate] = useState(formatDateYMD(initStartDate));
  const [startTime, setStartTime] = useState(formatTimeHM(initStartDate));
  const [endDate, setEndDate] = useState(formatDateYMD(initEndDate));
  const [endTime, setEndTime] = useState(formatTimeHM(initEndDate));

  // Determine initial scope
  const initialScope: CalendarScopeKind = event ? event.scope_kind : "personal";
  const [scopeKind, setScopeKind] = useState<CalendarScopeKind>(initialScope);
  const [workspaceId, setWorkspaceId] = useState<string>(
    event?.workspace_id ||
      sources.find((s) => s.kind !== "personal" && s.kind !== "site" && s.can_write)?.id ||
      "",
  );

  const initialColor =
    event?.color ||
    sources.find((s) => s.id === (scopeKind === "workspace" ? workspaceId : scopeKind))?.color ||
    "#1565c0";
  const [color, setColor] = useState(initialColor);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const panel = useRef<HTMLDivElement>(null);
  useFocusTrap(panel, true, onClose);

  const writableSources = sources.filter((s) => s.can_write);

  const handleScopeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === "personal" || val === "site") {
      setScopeKind(val);
      const src = sources.find((s) => s.id === val);
      if (src) setColor(src.color);
    } else {
      setScopeKind("workspace");
      setWorkspaceId(val);
      const src = sources.find((s) => s.id === val);
      if (src) setColor(src.color);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMsg("Please enter an event title.");
      return;
    }
    setErrorMsg(null);
    setSaving(true);
    try {
      await onSave({
        id: event?.id,
        revision: event?.revision,
        scope_kind: scopeKind,
        workspace_id: scopeKind === "workspace" ? workspaceId : "",
        title: title.trim(),
        description: description.trim(),
        location: location.trim(),
        start_date: startDate,
        start_time: allDay ? "00:00" : startTime,
        end_date: endDate,
        end_time: allDay ? "23:59" : endTime,
        all_day: allDay,
        color: color,
      });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save event.";
      setErrorMsg(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!event || !onDelete) return;
    if (!window.confirm("Are you sure you want to cancel this event?")) return;
    setSaving(true);
    try {
      await onDelete(event.id);
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete event.";
      setErrorMsg(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="cal-modal-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panel}
        tabIndex={-1}
        className="cal-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cal-modal-title"
      >
        <div className="cal-modal-header">
          <h3 id="cal-modal-title">{event ? "Edit Event" : "Create Event"}</h3>
          <button type="button" className="cal-modal-close-btn" onClick={onClose} aria-label="Close dialog">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="cal-modal-body">
            {errorMsg && (
              <div
                style={{
                  color: "#dc2626",
                  background: "#fef2f2",
                  padding: "8px 12px",
                  borderRadius: 6,
                  fontSize: "0.85rem",
                }}
                role="alert"
              >
                {errorMsg}
              </div>
            )}

            <div className="cal-form-group">
              <label htmlFor="cal-event-title">Event Title</label>
              <input
                id="cal-event-title"
                className="cal-input"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Add title (e.g., Weekly Lab Review, Seminar)"
                required
              />
            </div>

            <div className="cal-form-group">
              <label htmlFor="cal-scope-select">Calendar / Target Scope</label>
              <select
                id="cal-scope-select"
                className="cal-select"
                value={scopeKind === "workspace" ? workspaceId : scopeKind}
                onChange={handleScopeChange}
                disabled={Boolean(event)}
              >
                {writableSources.map((src) => (
                  <option key={src.id} value={src.id}>
                    {src.title} (
                    {src.kind === "personal"
                      ? "Private"
                      : src.kind === "site"
                        ? "Site"
                        : src.level || src.kind}
                    )
                  </option>
                ))}
              </select>
            </div>

            <div className="cal-form-group">
              <label
                htmlFor="cal-all-day-check"
                style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}
              >
                <input
                  id="cal-all-day-check"
                  type="checkbox"
                  checked={allDay}
                  onChange={(e) => setAllDay(e.target.checked)}
                />
                All day event
              </label>
            </div>

            <div className="cal-form-row">
              <div className="cal-form-group">
                <label htmlFor="cal-start-date">Start Date</label>
                <input
                  id="cal-start-date"
                  className="cal-input"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                />
              </div>
              {!allDay && (
                <div className="cal-form-group">
                  <label htmlFor="cal-start-time">Start Time (browser local)</label>
                  <input
                    id="cal-start-time"
                    className="cal-input"
                    type="time"
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    required
                  />
                </div>
              )}
            </div>

            <div className="cal-form-row">
              <div className="cal-form-group">
                <label htmlFor="cal-end-date">End Date</label>
                <input
                  id="cal-end-date"
                  className="cal-input"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                />
              </div>
              {!allDay && (
                <div className="cal-form-group">
                  <label htmlFor="cal-end-time">End Time (browser local)</label>
                  <input
                    id="cal-end-time"
                    className="cal-input"
                    type="time"
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    required
                  />
                </div>
              )}
            </div>

            <div className="cal-form-group">
              <label htmlFor="cal-location">Location / Venue</label>
              <input
                id="cal-location"
                className="cal-input"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Room number, lab bench, or meeting link"
              />
            </div>

            <div className="cal-form-group">
              <label htmlFor="cal-description">Description</label>
              <textarea
                id="cal-description"
                className="cal-textarea"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Meeting agenda, preparation notes, or discussion points"
              />
            </div>

            <div className="cal-form-group">
              <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "var(--text-muted)" }}>Color</span>
              <div className="cal-color-picker-row" role="group" aria-label="Event color choices">
                {PALETTE.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-label={`Select color ${c}`}
                    className={`cal-color-swatch ${color === c ? "active" : ""}`}
                    style={{ backgroundColor: c }}
                    onClick={() => setColor(c)}
                  />
                ))}
              </div>
            </div>
          </div>

          <div className="cal-modal-footer">
            {event && event.can_delete && onDelete ? (
              <button type="button" className="cal-btn-danger" onClick={handleDelete} disabled={saving}>
                Cancel event
              </button>
            ) : (
              <div />
            )}
            <div className="cal-modal-actions-right">
              <button type="button" className="cal-btn-secondary" onClick={onClose} disabled={saving}>
                Cancel
              </button>
              <button type="submit" className="cal-btn-primary" disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
