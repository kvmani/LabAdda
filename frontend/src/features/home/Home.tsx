import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { BASE } from "../../config";
import { fmtTime } from "../../format";
import { useSession } from "../../session";
import { useWorkspaces } from "../../workspaces";
import { Skeleton } from "../../ui";
import { Login } from "../../pages/Login";
import { BuildFooter } from "../shell/BuildFooter";
import { Brand } from "./Brand";
import { getDynamicGreeting } from "./greetings";
import { FaqSection } from "./FaqSection";
import { getDailySpark } from "./sparks";
import { ShortcutsModal } from "./ShortcutsModal";
import { useDashboardOverview, type Work } from "./useDashboardOverview";
import type { CalendarEvent } from "../calendar/types";
import "./home.css";

type PersonalNote = {
  id: string;
  title: string;
  body: string;
  due_at: string | null;
  remind_at: string | null;
  created_at: string;
  updated_at: string;
};

type FullTask = {
  id: string;
  title: string;
  description: string;
  due_date: string | null;
  priority: string;
  checklist: { title?: string; text?: string; done: boolean }[];
  revision: number;
  done: boolean;
  status: string;
};

const NOTE_TAGS = [
  { label: "Idea", icon: "💡", prefix: "[Idea] " },
  { label: "Experiment", icon: "🔬", prefix: "[Experiment] " },
  { label: "Reminder", icon: "📌", prefix: "[Reminder] " },
  { label: "Paper", icon: "📖", prefix: "[Paper] " },
];

/** Public welcome page; only fictional research artwork is visible before sign-in. */
export function Landing() {
  return (
    <main className="landing">
      <header className="landing__header">
        <Link to="/" aria-label="LabAdda home">
          <Brand />
        </Link>
        <nav aria-label="Welcome navigation">
          <a href="#features">Features</a>
          <Link to="/login">Sign in</Link>
        </nav>
      </header>
      <section className="landing__hero">
        <div>
          <h1>
            A place for ideas.
            <br />A space for your team.
          </h1>
          <p>A simple intranet collaboration platform for research teams.</p>
          <p>Your team’s work, on your organisation’s network.</p>
          <div className="landing__actions">
            <Link className="ui-button ui-button--primary ui-button--md" to="/login">
              Sign in
            </Link>
            <a className="ui-button ui-button--secondary ui-button--md" href="#features">
              Explore features
            </a>
          </div>
        </div>
        <figure>
          <img
            src={`${BASE}/research-board.png`}
            alt="Illustrative team whiteboard: tensile specimen, stress–strain curve and microstructure, with comments from fictional colleagues."
          />
          <figcaption>Structure Of Materials Section · Illustrative research discussion</figcaption>
        </figure>
      </section>
      <section id="features" className="landing__features" aria-label="Features">
        <article>
          <h2>Share updates</h2>
          <p>Keep notices, files and conversations with the right team.</p>
        </article>
        <article>
          <h2>Draw together</h2>
          <p>Sketch on a team whiteboard, or think privately on My Whiteboard.</p>
        </article>
        <article>
          <h2>Turn ideas into tasks</h2>
          <p>Capture next steps, assign work and follow progress.</p>
        </article>
      </section>
      <div style={{ maxWidth: "var(--landing-width)", margin: "0 auto", padding: "0 var(--space-6)" }}>
        <FaqSection defaultOpenId="official-platform" />
      </div>
      <Login next="/" embedded />
      <footer>
        <p>People, ideas and lab work.</p>
        <BuildFooter tone="inverse" />
      </footer>
    </main>
  );
}

function dueBadge(dueDate: string | null, today: string) {
  if (!dueDate) return null;
  if (dueDate < today) {
    return <span className="wb-badge wb-badge--overdue">Overdue ({dueDate})</span>;
  }
  if (dueDate === today) {
    return <span className="wb-badge wb-badge--due-today">Due today</span>;
  }
  return <span className="wb-badge wb-badge--due">Due {dueDate}</span>;
}

function priorityBadge(priority: string) {
  if (priority === "high") {
    return <span className="wb-badge wb-badge--priority-high">High</span>;
  }
  if (priority === "medium") {
    return <span className="wb-badge wb-badge--priority-medium">Medium</span>;
  }
  return <span className="wb-badge wb-badge--priority-low">Low</span>;
}

function formatEventTime(startsAt: string, endsAt: string, timezone: string): string {
  const start = fmtTime(startsAt, timezone);
  const end = fmtTime(endsAt, timezone);
  return `${start} – ${end}`;
}

/** Solidified Variation 1: Personal Workbench First Home Page */
export function Home() {
  const navigate = useNavigate();
  const { session } = useSession();
  const { workspaces, loading: workspacesLoading } = useWorkspaces();
  const { data: dashData, loading: dashLoading } = useDashboardOverview();

  const [notes, setNotes] = useState<PersonalNote[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [quickNoteTitle, setQuickNoteTitle] = useState("");
  const [quickNoteSaving, setQuickNoteSaving] = useState(false);
  const [quickNoteSuccess, setQuickNoteSuccess] = useState(false);
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const [todayEvents, setTodayEvents] = useState<CalendarEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const [showGuidelines, setShowGuidelines] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [sparkOffset, setSparkOffset] = useState(0);

  const [completedTaskIds, setCompletedTaskIds] = useState<Set<string>>(new Set());
  const [taskNotice, setTaskNotice] = useState<{ id: string; title: string; listId: string } | null>(null);

  const [spaceFilter, setSpaceFilter] = useState<"all" | "org" | "project" | "group">("all");
  const [spaceSearch, setSpaceSearch] = useState("");

  const noteInputRef = useRef<HTMLInputElement>(null);

  const spark = useMemo(() => getDailySpark(sparkOffset), [sparkOffset]);

  const greeting = useMemo(
    () => getDynamicGreeting(session?.user.display_name),
    [session?.user.display_name],
  );

  const todayFormatted = useMemo(() => {
    return new Intl.DateTimeFormat("en-IN", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date());
  }, []);

  // Fetch recent personal notes
  const loadNotes = useCallback(async () => {
    setNotesLoading(true);
    try {
      const res = await api<{ notes: PersonalNote[] }>("/notes");
      setNotes((res.notes || []).slice(0, 4));
    } catch {
      // Notes fallback
    } finally {
      setNotesLoading(false);
    }
  }, []);

  // Fetch today's calendar events
  const loadTodayEvents = useCallback(async () => {
    setEventsLoading(true);
    try {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0).toISOString();
      const end = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999).toISOString();
      const events = await api<CalendarEvent[]>("/calendar/events", {
        params: { start, end },
      });
      setTodayEvents(events || []);
    } catch {
      // Events fallback
    } finally {
      setEventsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadNotes();
    void loadTodayEvents();
  }, [loadNotes, loadTodayEvents]);

  // Global keyboard shortcuts on Home page
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isInput =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);

      if (e.key === "?" && !isInput) {
        e.preventDefault();
        setShowShortcuts((prev) => !prev);
      } else if (!isInput && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (e.key === "n" || e.key === "N") {
          e.preventDefault();
          noteInputRef.current?.focus();
        } else if (e.key === "w" || e.key === "W") {
          e.preventDefault();
          navigate("/whiteboard");
        } else if (e.key === "t" || e.key === "T") {
          e.preventDefault();
          navigate("/my-tasks");
        } else if (e.key === "c" || e.key === "C") {
          e.preventDefault();
          navigate("/calendar");
        } else if (e.key === "o" || e.key === "O") {
          e.preventDefault();
          navigate("/notes");
        } else if (e.key === "s" || e.key === "S") {
          e.preventDefault();
          setSparkOffset((prev) => prev + 1);
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate]);

  async function handleQuickNote(e: FormEvent) {
    e.preventDefault();
    const title = quickNoteTitle.trim();
    if (!title) return;
    setQuickNoteSaving(true);
    try {
      const created = await api<PersonalNote>("/notes", {
        body: { title, body: "" },
      });
      setNotes((prev) => [created, ...prev.filter((n) => n.id !== created.id)].slice(0, 4));
      setQuickNoteTitle("");
      setActiveTag(null);
      setQuickNoteSuccess(true);
      setTimeout(() => setQuickNoteSuccess(false), 3000);
    } catch {
      // Ignore note error
    } finally {
      setQuickNoteSaving(false);
    }
  }

  function handleTagClick(prefix: string, tagLabel: string) {
    if (activeTag === tagLabel) {
      setActiveTag(null);
      if (quickNoteTitle.startsWith(prefix)) {
        setQuickNoteTitle(quickNoteTitle.slice(prefix.length));
      }
    } else {
      setActiveTag(tagLabel);
      let cleaned = quickNoteTitle;
      for (const t of NOTE_TAGS) {
        if (cleaned.startsWith(t.prefix)) {
          cleaned = cleaned.slice(t.prefix.length);
        }
      }
      setQuickNoteTitle(prefix + cleaned);
    }
    noteInputRef.current?.focus();
  }

  async function toggleTaskComplete(task: Work) {
    if (completedTaskIds.has(task.id)) return;
    // Optimistic completion
    setCompletedTaskIds((prev) => new Set(prev).add(task.id));
    setTaskNotice({ id: task.id, title: task.title, listId: task.list_id });

    try {
      const full = await api<FullTask>(`/todos/lists/${task.list_id}/tasks/${task.id}`);
      await api(`/todos/lists/${task.list_id}/tasks/${task.id}`, {
        method: "PUT",
        body: {
          title: full.title,
          description: full.description || "",
          due_date: full.due_date,
          priority: full.priority,
          checklist: (full.checklist || []).map((c) => ({
            title: c.title || c.text || "Item",
            done: !!c.done,
          })),
          revision: full.revision,
          done: true,
          status: "done",
        },
      });
    } catch {
      // Revert if API fails
      setCompletedTaskIds((prev) => {
        const next = new Set(prev);
        next.delete(task.id);
        return next;
      });
      setTaskNotice(null);
    }
  }

  async function undoTaskComplete() {
    if (!taskNotice) return;
    const { id, listId } = taskNotice;
    setCompletedTaskIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
    setTaskNotice(null);

    try {
      const full = await api<FullTask>(`/todos/lists/${listId}/tasks/${id}`);
      await api(`/todos/lists/${listId}/tasks/${id}`, {
        method: "PUT",
        body: {
          title: full.title,
          description: full.description || "",
          due_date: full.due_date,
          priority: full.priority,
          checklist: (full.checklist || []).map((c) => ({
            title: c.title || c.text || "Item",
            done: !!c.done,
          })),
          revision: full.revision,
          done: false,
          status: "todo",
        },
      });
    } catch {
      // Revert silently
    }
  }

  const tasks: Work[] = dashData?.tasks || [];
  const activeTasks = tasks.filter((t) => !completedTaskIds.has(t.id));
  const todayStr = dashData?.today || new Date().toISOString().slice(0, 10);
  const timezone = dashData?.timezone || "Asia/Kolkata";

  // Filtered workspaces
  const filteredWorkspaces = useMemo(() => {
    return workspaces.filter((ws) => {
      if (spaceFilter !== "all" && ws.kind !== spaceFilter) return false;
      if (spaceSearch.trim()) {
        const query = spaceSearch.toLowerCase();
        return ws.name.toLowerCase().includes(query) || (ws.description || "").toLowerCase().includes(query);
      }
      return true;
    });
  }, [workspaces, spaceFilter, spaceSearch]);

  const orgCount = workspaces.filter((w) => w.kind === "org").length;
  const projectCount = workspaces.filter((w) => w.kind === "project").length;
  const groupCount = workspaces.filter((w) => w.kind === "group").length;

  return (
    <main className="wb-home" tabIndex={-1}>
      {/* 1. Collegiate Hero Greeting & Personal Status Bar */}
      <section className="wb-hero" aria-label="Welcome and today's summary">
        <div className="wb-hero__main">
          <div className="wb-hero__greeting-container">
            <h1 className="wb-hero__greeting">{greeting}</h1>
            <p className="wb-hero__date">
              <span className="wb-hero__date-icon" aria-hidden="true">📅</span>
              <span>{todayFormatted}</span>
              <span className="wb-hero__separator" aria-hidden="true">·</span>
              <span className="wb-airgap-pill">
                <span className="wb-airgap-pill__dot" aria-hidden="true" />
                Air-gapped Lab Intranet
              </span>
            </p>
          </div>
          <div className="wb-hero__actions">
            <Link to="/whiteboard" className="wb-hero__cta-btn">
              <span className="wb-hero__cta-icon" aria-hidden="true">🎨</span>
              <span>Open My Whiteboard</span>
            </Link>
          </div>
        </div>

        {/* Quick status summary chips & Shortcuts button */}
        <div className="wb-hero__stats" role="region" aria-label="Quick counts and tools">
          <Link to="/my-tasks" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">📋</span>
            <span className="wb-stat-chip__count">{activeTasks.length}</span>
            <span className="wb-stat-chip__label">Active Tasks</span>
          </Link>
          <Link to="/calendar" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">🗓️</span>
            <span className="wb-stat-chip__count">{todayEvents.length}</span>
            <span className="wb-stat-chip__label">Today’s Events</span>
          </Link>
          <Link to="/notes" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">📝</span>
            <span className="wb-stat-chip__count">{notes.length}</span>
            <span className="wb-stat-chip__label">Private Notes</span>
          </Link>
          <a href="#workspaces" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">🏢</span>
            <span className="wb-stat-chip__count">{workspaces.length}</span>
            <span className="wb-stat-chip__label">Workspaces</span>
          </a>
          <button
            type="button"
            className="wb-stat-chip wb-stat-chip--shortcuts"
            onClick={() => setShowShortcuts(true)}
            aria-label="Open keyboard shortcuts cheat-sheet (Press ?)"
          >
            <span className="wb-stat-chip__icon" aria-hidden="true">⌨️</span>
            <span className="wb-stat-chip__label">Shortcuts <kbd>?</kbd></span>
          </button>
        </div>
      </section>

      {/* 2. Daily Research Spark / Scientific Inspiration */}
      <section className="wb-spark-banner" aria-label="Daily scientific inspiration">
        <div className="wb-spark-banner__left">
          <span className="wb-spark-banner__tag">
            <span aria-hidden="true">🔬</span> Research Spark
          </span>
          <blockquote className="wb-spark-banner__quote">
            “{spark.quote}”
            <footer className="wb-spark-banner__author">
              — <strong>{spark.author}</strong>
              {spark.context && <span className="wb-spark-banner__context"> · {spark.context}</span>}
            </footer>
          </blockquote>
        </div>
        <button
          type="button"
          className="wb-spark-banner__btn"
          onClick={() => setSparkOffset((prev) => prev + 1)}
          title="Cycle to another research spark (Press S)"
          aria-label="Cycle to another research spark"
        >
          ✨ Another spark
        </button>
      </section>

      {/* 3. Collapsible Lab Collaboration Guidelines */}
      <section className="wb-guidance" aria-label="LabAdda collaboration guidelines">
        <div className="wb-guidance__bar">
          <div className="wb-guidance__summary">
            <span className="wb-guidance__icon" aria-hidden="true">🤝</span>
            <div>
              <strong className="wb-guidance__title">LabAdda Guidelines:</strong>
              <span className="wb-guidance__teaser"> Digital lab whiteboard · Zero sensitive data · Lightweight files · Constructive teamwork</span>
            </div>
          </div>
          <button
            type="button"
            className="wb-guidance__toggle-btn"
            onClick={() => setShowGuidelines((prev) => !prev)}
            aria-expanded={showGuidelines}
          >
            {showGuidelines ? "Hide guidelines ▲" : "Read guidelines ▼"}
          </button>
        </div>

        {showGuidelines && (
          <div className="wb-guidance__body">
            <p className="wb-guidance__intro">
              LabAdda is our internal digital whiteboard experiment designed for effortless day-to-day collaboration:
            </p>
            <ul className="wb-guidance__list">
              <li>
                <strong>Digital whiteboard for the lab:</strong> This is an informal, collaborative workspace for day-to-day lab ideas and quick drafts. It is not an official organizational reporting platform.
              </li>
              <li>
                <strong>No sensitive or official data:</strong> LabAdda is strictly for informal lab ideas, sketches, and task tracking. Never upload classified, sensitive, or official organizational records here.
              </li>
              <li>
                <strong>Keep files light and relevant:</strong> Upload only necessary work-related diagrams and references. Avoiding huge attachments keeps our local intranet server fast and responsive.
              </li>
              <li>
                <strong>Warm and constructive etiquette:</strong> We thrive on mutual respect. Communicate with warmth, professional courtesy, and constructive suggestions.
              </li>
            </ul>
          </div>
        )}
      </section>

      {/* 4. Whiteboard Hero Banner (Top Personal Feature) */}
      <section className="wb-whiteboard-banner" aria-label="My Whiteboard Quick Access">
        <div className="wb-whiteboard-banner__content">
          <div className="wb-whiteboard-banner__tag">Private Thinking Space</div>
          <h2 className="wb-whiteboard-banner__title">My Whiteboard</h2>
          <p className="wb-whiteboard-banner__desc">
            Your personal, persistent canvas for brainstorming, freehand sketching, chemical structures, and sticky notes. Everything here is strictly private to you.
          </p>
          <div className="wb-whiteboard-banner__actions">
            <Link to="/whiteboard" className="ui-button ui-button--primary ui-button--md">
              Open Canvas →
            </Link>
            <Link to="/calendar" className="ui-button ui-button--secondary ui-button--md">
              View Calendar
            </Link>
          </div>
          {/* Quick template triggers */}
          <div className="wb-whiteboard-banner__templates" aria-label="Whiteboard quick launch templates">
            <span className="wb-whiteboard-banner__templates-label">Quick start:</span>
            <Link to="/whiteboard" className="wb-template-pill" title="Open blank whiteboard">
              🎨 Blank Canvas
            </Link>
            <Link to="/whiteboard" className="wb-template-pill" title="Start with sticky notes">
              📝 Sticky Notes
            </Link>
            <Link to="/whiteboard" className="wb-template-pill" title="Draw flowchart or reaction">
              📊 Flow & Diagram
            </Link>
          </div>
        </div>
        <div className="wb-whiteboard-banner__illustration" aria-hidden="true">
          <div className="wb-canvas-preview">
            <div className="wb-canvas-preview__sticky wb-canvas-preview__sticky--yellow">
              <span>💡 Experiment notes</span>
            </div>
            <div className="wb-canvas-preview__sticky wb-canvas-preview__sticky--cyan">
              <span>🔬 Coating trial α</span>
            </div>
            <div className="wb-canvas-preview__curve">
              <svg viewBox="0 0 120 40" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M5 30 C 35 5, 80 35, 115 10" />
              </svg>
            </div>
            <div className="wb-canvas-preview__badge">Personal · Auto-saved</div>
          </div>
        </div>
      </section>

      {/* 5. Responsive 2-Column Personal Workbench Grid */}
      <div className="wb-grid">
        {/* LEFT COLUMN: Tasks & Calendar Agenda */}
        <div className="wb-grid__col wb-grid__col--main">
          {/* Card: Active Tasks & Today's Deadlines with Inline Completion */}
          <section className="wb-card" aria-label="Active tasks and deadlines">
            <div className="wb-card__header">
              <div>
                <h2 className="wb-card__title">
                  <span className="wb-card__icon" aria-hidden="true">📋</span>
                  <span>My Tasks & Deadlines</span>
                </h2>
                <p className="wb-card__subtitle">Click checkbox to mark complete · Synced with team lists</p>
              </div>
              <Link to="/my-tasks" className="wb-card__link">
                View all ({activeTasks.length}) →
              </Link>
            </div>

            <div className="wb-card__body">
              {/* Task Completed Feedback Toast */}
              {taskNotice && (
                <div className="wb-task-toast" role="status">
                  <span>✓ <strong>{taskNotice.title}</strong> marked as completed!</span>
                  <button type="button" className="wb-task-toast__undo" onClick={undoTaskComplete}>
                    Undo
                  </button>
                </div>
              )}

              {dashLoading ? (
                <Skeleton label="Loading your tasks" />
              ) : activeTasks.length === 0 ? (
                <div className="wb-empty">
                  <p className="wb-empty__text">🎉 No pending tasks for today. You’re all caught up!</p>
                  <Link to="/todos" className="ui-button ui-button--secondary ui-button--sm">
                    + Create a task
                  </Link>
                </div>
              ) : (
                <ul className="wb-task-list">
                  {activeTasks.map((task) => {
                    const isDone = completedTaskIds.has(task.id);
                    return (
                      <li key={task.id} className={`wb-task-item ${isDone ? "wb-task-item--done" : ""}`}>
                        <button
                          type="button"
                          className="wb-task-checkbox"
                          onClick={() => toggleTaskComplete(task)}
                          title="Mark task as completed"
                          aria-label={`Mark task completed: ${task.title}`}
                        >
                          <span className="wb-task-checkbox__mark" aria-hidden="true">✓</span>
                        </button>
                        <div className="wb-task-item__content">
                          <Link
                            to={task.workspace_id ? `/w/${task.workspace_id}/todos` : "/todos"}
                            className="wb-task-item__title"
                          >
                            {task.title}
                          </Link>
                          <div className="wb-task-item__meta">
                            {priorityBadge(task.priority)}
                            {dueBadge(task.due_date, todayStr)}
                            <span className="wb-task-item__space">
                              {task.workspace_name ? (
                                <Link to={`/w/${task.workspace_id}/todos`}>{task.workspace_name}</Link>
                              ) : (
                                "Private list"
                              )}
                              {" · "}
                              {task.list_title}
                            </span>
                          </div>
                        </div>
                        <Link
                          to={task.workspace_id ? `/w/${task.workspace_id}/todos` : "/todos"}
                          className="wb-task-item__action"
                          aria-label={`Open task: ${task.title}`}
                        >
                          Open →
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>

          {/* Card: Today's Schedule & Events */}
          <section className="wb-card" aria-label="Today's schedule">
            <div className="wb-card__header">
              <div>
                <h2 className="wb-card__title">
                  <span className="wb-card__icon" aria-hidden="true">🗓️</span>
                  <span>Today’s Schedule</span>
                </h2>
                <p className="wb-card__subtitle">Seminars, meetings and deadlines for {todayFormatted}</p>
              </div>
              <Link to="/calendar" className="wb-card__link">
                Open Calendar →
              </Link>
            </div>

            <div className="wb-card__body">
              {eventsLoading ? (
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
                              <span className="wb-hero__separator" aria-hidden="true">·</span>
                            </span>
                          )}
                          <span className="wb-badge wb-badge--scope">
                            {ev.scope_kind === "site"
                              ? "Site-wide"
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
        </div>

        {/* RIGHT COLUMN: Quick Notes & Team Workspaces */}
        <div className="wb-grid__col wb-grid__col--side">
          {/* Card: Quick Notes & Personal Scratchpad with Category Tags */}
          <section className="wb-card" aria-label="My Notes and quick jot">
            <div className="wb-card__header">
              <div>
                <h2 className="wb-card__title">
                  <span className="wb-card__icon" aria-hidden="true">📝</span>
                  <span>My Notes</span>
                </h2>
                <p className="wb-card__subtitle">Private reminders · Press N to jot quickly</p>
              </div>
              <Link to="/notes" className="wb-card__link">
                All notes →
              </Link>
            </div>

            <div className="wb-card__body">
              {/* Quick Tag Pills */}
              <div className="wb-tag-pills" role="region" aria-label="Note category tags">
                {NOTE_TAGS.map((tag) => {
                  const isSelected = activeTag === tag.label;
                  return (
                    <button
                      key={tag.label}
                      type="button"
                      className={`wb-tag-pill ${isSelected ? "wb-tag-pill--selected" : ""}`}
                      onClick={() => handleTagClick(tag.prefix, tag.label)}
                      title={`Add ${tag.label} prefix`}
                    >
                      <span aria-hidden="true">{tag.icon}</span> {tag.label}
                    </button>
                  );
                })}
              </div>

              {/* Quick Jot input form */}
              <form onSubmit={handleQuickNote} className="wb-quick-note-form">
                <label htmlFor="quick-note-input" className="wb-sr-only">
                  Quick note or reminder
                </label>
                <div className="wb-quick-note-input-row">
                  <input
                    ref={noteInputRef}
                    id="quick-note-input"
                    type="text"
                    className="wb-quick-note-input"
                    placeholder="Jot a quick note or reminder... (Press Enter)"
                    value={quickNoteTitle}
                    onChange={(e) => setQuickNoteTitle(e.target.value)}
                    maxLength={200}
                    disabled={quickNoteSaving}
                  />
                  <button
                    type="submit"
                    className="wb-quick-note-btn"
                    disabled={quickNoteSaving || !quickNoteTitle.trim()}
                    aria-label="Add note"
                  >
                    {quickNoteSaving ? "..." : "+ Jot"}
                  </button>
                </div>
                {quickNoteSuccess && (
                  <p className="wb-quick-note-feedback" role="status">
                    ✓ Saved to your private notes!
                  </p>
                )}
              </form>

              {/* Recent notes list */}
              {notesLoading ? (
                <Skeleton label="Loading notes" />
              ) : notes.length === 0 ? (
                <div className="wb-empty wb-empty--compact">
                  <p className="wb-empty__text">No notes yet. Jot down an idea above!</p>
                </div>
              ) : (
                <ul className="wb-note-list">
                  {notes.map((note) => (
                    <li key={note.id} className="wb-note-item">
                      <Link to="/notes" className="wb-note-item__link">
                        <strong className="wb-note-item__title">{note.title || "Untitled note"}</strong>
                        {note.body && <p className="wb-note-item__body">{note.body}</p>}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          {/* Card: Accessible Team Spaces with Filters & Search */}
          <section id="workspaces" className="wb-card" aria-label="Your team workspaces">
            <div className="wb-card__header">
              <div>
                <h2 className="wb-card__title">
                  <span className="wb-card__icon" aria-hidden="true">🏢</span>
                  <span>Your Team Spaces</span>
                </h2>
                <p className="wb-card__subtitle">Divisions, sections, projects & groups</p>
              </div>
              <Link to="/groups/new" className="wb-card__link">
                + New group
              </Link>
            </div>

            <div className="wb-card__body">
              {/* Space category filters */}
              <div className="wb-space-filters" role="tablist" aria-label="Workspace filters">
                <button
                  type="button"
                  role="tab"
                  aria-selected={spaceFilter === "all"}
                  className={`wb-space-filter-btn ${spaceFilter === "all" ? "wb-space-filter-btn--active" : ""}`}
                  onClick={() => setSpaceFilter("all")}
                >
                  All ({workspaces.length})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={spaceFilter === "org"}
                  className={`wb-space-filter-btn ${spaceFilter === "org" ? "wb-space-filter-btn--active" : ""}`}
                  onClick={() => setSpaceFilter("org")}
                >
                  Units ({orgCount})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={spaceFilter === "project"}
                  className={`wb-space-filter-btn ${spaceFilter === "project" ? "wb-space-filter-btn--active" : ""}`}
                  onClick={() => setSpaceFilter("project")}
                >
                  Projects ({projectCount})
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={spaceFilter === "group"}
                  className={`wb-space-filter-btn ${spaceFilter === "group" ? "wb-space-filter-btn--active" : ""}`}
                  onClick={() => setSpaceFilter("group")}
                >
                  Groups ({groupCount})
                </button>
              </div>

              {/* Search filter if workspaces > 3 */}
              {workspaces.length > 3 && (
                <div className="wb-space-search-box">
                  <input
                    type="search"
                    className="wb-space-search-input"
                    placeholder="Filter spaces by name..."
                    value={spaceSearch}
                    onChange={(e) => setSpaceSearch(e.target.value)}
                    aria-label="Filter workspaces by name"
                  />
                  {spaceSearch && (
                    <button
                      type="button"
                      className="wb-space-search-clear"
                      onClick={() => setSpaceSearch("")}
                      aria-label="Clear space search"
                    >
                      ✕
                    </button>
                  )}
                </div>
              )}

              {workspacesLoading ? (
                <Skeleton label="Loading team spaces" />
              ) : filteredWorkspaces.length === 0 ? (
                <div className="wb-empty wb-empty--compact">
                  <p className="wb-empty__text">
                    {spaceSearch ? "No spaces match your filter." : "No spaces in this category."}
                  </p>
                  {spaceSearch && (
                    <button
                      type="button"
                      className="ui-button ui-button--quiet ui-button--sm"
                      onClick={() => setSpaceSearch("")}
                    >
                      Clear search
                    </button>
                  )}
                </div>
              ) : (
                <ul className="wb-space-list">
                  {filteredWorkspaces.map((ws) => (
                    <li key={ws.id} className="wb-space-item">
                      <div className="wb-space-item__main">
                        <Link to={`/w/${ws.id}/noticeboard`} className="wb-space-item__name">
                          {ws.kind === "project" && <span className="wb-space-kind-icon" aria-hidden="true">🚀 </span>}
                          {ws.kind === "group" && <span className="wb-space-kind-icon" aria-hidden="true">👥 </span>}
                          {ws.kind === "org" && <span className="wb-space-kind-icon" aria-hidden="true">🏢 </span>}
                          {ws.name}
                        </Link>
                      </div>
                      <div className="wb-space-item__quick-nav">
                        <Link to={`/w/${ws.id}/noticeboard`} title="Noticeboard">
                          Noticeboard
                        </Link>
                        <span>·</span>
                        <Link to={`/w/${ws.id}/whiteboard`} title="Whiteboard">
                          Board
                        </Link>
                        <span>·</span>
                        <Link to={`/w/${ws.id}/chat`} title="Chat">
                          Chat
                        </Link>
                        <span>·</span>
                        <Link to={`/w/${ws.id}/todos`} title="Tasks">
                          Tasks
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* 6. Comprehensive FAQ Accordion */}
      <section className="wb-faq-container" aria-label="Frequently Asked Questions">
        <FaqSection />
      </section>

      {/* 7. Keyboard Shortcuts Modal */}
      <ShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />
    </main>
  );
}
