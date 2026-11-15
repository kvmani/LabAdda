import React, { useState } from "react";
import { CalendarEvent, CalendarScopeKind, CalendarSource, EventFormData } from "./types";

type Props = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: EventFormData) => Promise<void>;
  onDelete?: (eventId: string) => Promise<void>;
  event: CalendarEvent | null;
  defaultDate?: Date;
  sources: CalendarSource[];
};

const PALETTE = [
  "#d81b60", // Rose
  "#1565c0", // Navy
  "#00838f", // Teal
  "#2e7d32", // Forest Green
  "#ef6c00", // Orange
  "#6a1b9a", // Deep Purple
  "#c62828", // Crimson
  "#455a64", // Slate
];

export const EventDialog: React.FC<Props> = ({
  isOpen,
  onClose,
  onSave,
  onDelete,
  event,
  defaultDate,
  sources,
}) => {
  if (!isOpen) return null;

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

  const initStartDate = event
    ? new Date(event.starts_at)
    : defaultDate || new Date();
  const initEndDate = event
    ? new Date(event.ends_at)
    : new Date(initStartDate.getTime() + 60 * 60 * 1000);

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
      ""
  );

  const initialColor = event?.color || sources.find((s) => s.id === (scopeKind === "workspace" ? workspaceId : scopeKind))?.color || "#1565c0";
  const [color, setColor] = useState(initialColor);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
    if (!window.confirm("Are you sure you want to delete this event?")) return;
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
    <div className="cal-modal-backdrop" onClick={onClose}>
      <div className="cal-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="cal-modal-header">
          <h3>{event ? "Edit Event" : "Create Event"}</h3>
          <button className="cal-modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="cal-modal-body">
            {errorMsg && (
              <div style={{ color: "#dc2626", background: "#fef2f2", padding: "8px 12px", borderRadius: 6, fontSize: "0.85rem" }}>
                {errorMsg}
              </div>
            )}

            <div className="cal-form-group">
              <label>Event Title</label>
              <input
                className="cal-input"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Add title (e.g., Weekly Lab Review, Seminar)"
                autoFocus
                required
              />
            </div>

            <div className="cal-form-group">
              <label>Calendar / Target Scope</label>
              <select
                className="cal-select"
                value={scopeKind === "workspace" ? workspaceId : scopeKind}
                onChange={handleScopeChange}
                disabled={Boolean(event)}
              >
                {writableSources.map((src) => (
                  <option key={src.id} value={src.id}>
                    {src.title} ({src.kind === "personal" ? "Private" : src.kind === "site" ? "Site" : src.level || src.kind})
                  </option>
                ))}
              </select>
            </div>

            <div className="cal-form-group">
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={allDay}
                  onChange={(e) => setAllDay(e.target.checked)}
                />
                All day event
              </label>
            </div>

            <div className="cal-form-row">
              <div className="cal-form-group">
                <label>Start Date</label>
                <input
                  className="cal-input"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  required
                />
              </div>
              {!allDay && (
                <div className="cal-form-group">
                  <label>Start Time (IST)</label>
                  <input
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
                <label>End Date</label>
                <input
                  className="cal-input"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  required
                />
              </div>
              {!allDay && (
                <div className="cal-form-group">
                  <label>End Time (IST)</label>
                  <input
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
              <label>Location / Venue</label>
              <input
                className="cal-input"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Room number, lab bench, or meeting link"
              />
            </div>

            <div className="cal-form-group">
              <label>Description</label>
              <textarea
                className="cal-textarea"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Meeting agenda, preparation notes, or discussion points"
              />
            </div>

            <div className="cal-form-group">
              <label>Color</label>
              <div className="cal-color-picker-row">
                {PALETTE.map((c) => (
                  <span
                    key={c}
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
              <button
                type="button"
                className="cal-btn-danger"
                onClick={handleDelete}
                disabled={saving}
              >
                Delete
              </button>
            ) : <div />}
            <div className="cal-modal-actions-right">
              <button
                type="button"
                className="cal-btn-secondary"
                onClick={onClose}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="cal-btn-primary"
                disabled={saving}
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
