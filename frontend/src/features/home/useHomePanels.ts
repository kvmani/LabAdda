import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../../api";
import { invalidate } from "../../generation";
import type { CalendarEvent } from "../calendar/types";
import { dayRange } from "./homeDates";

export type PersonalNote = {
  id: string;
  title: string;
  body: string;
  due_at: string | null;
  remind_at: string | null;
  created_at: string;
  updated_at: string;
};

/** Clear protected agenda rows on access changes and ignore late responses from older scopes. */
export function useHomePanels(scopeKey: string, day: string, timezone: string) {
  const [notes, setNotes] = useState<PersonalNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesError, setNotesError] = useState("");
  const [eventData, setEvents] = useState<{ scope: string; rows: CalendarEvent[] }>({
    scope: scopeKey,
    rows: [],
  });
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState("");
  const notesGeneration = useRef(0);
  const eventsGeneration = useRef(0);
  const loadNotes = useCallback(async () => {
    const token = ++notesGeneration.current;
    setNotesLoading(true);
    setNotesError("");
    try {
      const result = await api<{ notes: PersonalNote[] }>("/notes");
      if (token === notesGeneration.current) setNotes(result.notes.slice(0, 4));
    } catch (error: unknown) {
      if (token === notesGeneration.current) setNotesError(errorMessage(error));
    } finally {
      if (token === notesGeneration.current) setNotesLoading(false);
    }
  }, []);
  const loadEvents = useCallback(async () => {
    const token = ++eventsGeneration.current;
    setEventsLoading(true);
    setEventsError("");
    try {
      const result = await api<CalendarEvent[]>("/calendar/events", { params: dayRange(day, timezone) });
      if (token === eventsGeneration.current) setEvents({ scope: scopeKey, rows: result });
    } catch (error: unknown) {
      if (token === eventsGeneration.current) setEventsError(errorMessage(error));
    } finally {
      if (token === eventsGeneration.current) setEventsLoading(false);
    }
  }, [day, timezone, scopeKey]);
  useEffect(() => {
    setEvents({ scope: scopeKey, rows: [] });
    setNotes([]);
    void loadEvents();
    void loadNotes();
    const timer = window.setInterval(() => {
      if (!document.hidden) {
        void loadEvents();
        void loadNotes();
      }
    }, 30000);
    return () => {
      invalidate(notesGeneration);
      invalidate(eventsGeneration);
      window.clearInterval(timer);
    };
  }, [scopeKey, loadEvents, loadNotes]);
  const addNote = useCallback((note: PersonalNote) => {
    invalidate(notesGeneration);
    setNotesLoading(false);
    setNotesError("");
    setNotes((previous) => [note, ...previous.filter((row) => row.id !== note.id)].slice(0, 4));
  }, []);
  return {
    notes,
    notesLoading,
    notesError,
    loadNotes,
    events: eventData.scope === scopeKey ? eventData.rows : [],
    eventsLoading,
    eventsError,
    loadEvents,
    addNote,
  };
}
