import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../../session";
import { useWorkspaces } from "../../workspaces";
import { getDynamicGreeting } from "./greetings";
import { FaqSection } from "./FaqSection";
import { getDailySpark } from "./sparks";
import { ShortcutsModal } from "./ShortcutsModal";
import { useDashboardOverview } from "./useDashboardOverview";
import { useHomeTasks } from "./useHomeTasks";
import { useHomePanels } from "./useHomePanels";
import { siteDay } from "./homeDates";
import { HomeTasksCard } from "./HomeTasksCard";
import { HomeAgendaCard } from "./HomeAgendaCard";
import { HomeNotesCard } from "./HomeNotesCard";
import { HomeSpacesCard } from "./HomeSpacesCard";
export { Landing } from "./Landing";
import "./home.css";

/** Personal workbench: current grants, confirmed saves and site-local dates. */
export function Home() {
  const navigate = useNavigate();
  const { session } = useSession();
  const { workspaces } = useWorkspaces();
  const dashboard = useDashboardOverview();
  const { data: dashData, accessVersion } = dashboard;
  const [clock, setClock] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 60000);
    return () => window.clearInterval(timer);
  }, []);
  const timezone = session?.timezone ?? "Asia/Kolkata";
  const todayStr = siteDay(clock, timezone);
  const scopeKey =
    workspaces
      .map((workspace) => workspace.id)
      .sort()
      .join("|") +
    ":" +
    accessVersion;
  const panels = useHomePanels(scopeKey, todayStr, timezone);
  const { notes, notesLoading, notesError, events: allEvents, eventsLoading, eventsError } = panels;
  const taskActions = useHomeTasks(dashboard.load, scopeKey);
  const todayEvents = allEvents.filter(
    (event) =>
      event.scope_kind !== "workspace" || workspaces.some((space) => space.id === event.workspace_id),
  );
  const [showGuidelines, setShowGuidelines] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [sparkOffset, setSparkOffset] = useState(0);

  const noteInputRef = useRef<HTMLInputElement>(null);

  const spark = useMemo(() => getDailySpark(sparkOffset), [sparkOffset]);

  const greeting = useMemo(
    () => getDynamicGreeting(session?.user.display_name),
    [session?.user.display_name],
  );

  const todayFormatted = new Intl.DateTimeFormat("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: timezone,
  }).format(clock);

  // Global keyboard shortcuts on Home page
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (showShortcuts) return;
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
          void navigate("/whiteboard");
        } else if (e.key === "t" || e.key === "T") {
          e.preventDefault();
          void navigate("/my-tasks");
        } else if (e.key === "c" || e.key === "C") {
          e.preventDefault();
          void navigate("/calendar");
        } else if (e.key === "o" || e.key === "O") {
          e.preventDefault();
          void navigate("/notes");
        } else if (e.key === "s" || e.key === "S") {
          e.preventDefault();
          setSparkOffset((prev) => prev + 1);
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [navigate, showShortcuts]);

  const tasks = dashData?.tasks || [];
  const activeTasks = tasks.filter(
    (task) =>
      task.status !== "done" &&
      (!task.workspace_id || workspaces.some((space) => space.id === task.workspace_id)),
  );

  return (
    <main className="wb-home" tabIndex={-1}>
      {/* 1. Collegiate Hero Greeting & Personal Status Bar */}
      <section className="wb-hero" aria-label="Welcome and today's summary">
        <div className="wb-hero__main">
          <div className="wb-hero__greeting-container">
            <h1 className="wb-hero__greeting">{greeting}</h1>
            <p className="wb-hero__date">
              <span className="wb-hero__date-icon" aria-hidden="true">
                📅
              </span>
              <span>{todayFormatted}</span>
              <span className="wb-hero__separator" aria-hidden="true">
                ·
              </span>
              <span className="wb-airgap-pill">
                <span className="wb-airgap-pill__dot" aria-hidden="true" />
                Air-gapped Lab Intranet
              </span>
            </p>
          </div>
          <div className="wb-hero__actions">
            <Link to="/whiteboard" className="wb-hero__cta-btn">
              <span className="wb-hero__cta-icon" aria-hidden="true">
                🎨
              </span>
              <span>Open My Whiteboard</span>
            </Link>
          </div>
        </div>

        {/* Quick status summary chips & Shortcuts button */}
        <div className="wb-hero__stats" role="region" aria-label="Quick counts and tools">
          <Link to="/my-tasks" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">
              📋
            </span>
            <span className="wb-stat-chip__count">
              {dashData ? `${activeTasks.length}${dashData.tasks_more ? "+" : ""}` : "—"}
            </span>
            <span className="wb-stat-chip__label">Active Tasks</span>
          </Link>
          <Link to="/calendar" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">
              🗓️
            </span>
            <span className="wb-stat-chip__count">
              {eventsLoading || eventsError ? "—" : todayEvents.length}
            </span>
            <span className="wb-stat-chip__label">Today’s Events</span>
          </Link>
          <Link to="/notes" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">
              📝
            </span>
            <span className="wb-stat-chip__count">{notesLoading || notesError ? "—" : notes.length}</span>
            <span className="wb-stat-chip__label">Recent Notes</span>
          </Link>
          <a href="#workspaces" className="wb-stat-chip">
            <span className="wb-stat-chip__icon" aria-hidden="true">
              🏢
            </span>
            <span className="wb-stat-chip__count">{workspaces.length}</span>
            <span className="wb-stat-chip__label">Workspaces</span>
          </a>
          <button
            type="button"
            className="wb-stat-chip wb-stat-chip--shortcuts"
            onClick={() => setShowShortcuts(true)}
            aria-label="Open keyboard shortcuts cheat-sheet (Press ?)"
          >
            <span className="wb-stat-chip__icon" aria-hidden="true">
              ⌨️
            </span>
            <span className="wb-stat-chip__label">
              Shortcuts <kbd>?</kbd>
            </span>
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
            <span className="wb-guidance__icon" aria-hidden="true">
              🤝
            </span>
            <div>
              <strong className="wb-guidance__title">LabAdda Guidelines:</strong>
              <span className="wb-guidance__teaser">
                {" "}
                Digital lab whiteboard · Zero sensitive data · Lightweight files · Constructive teamwork
              </span>
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
              LabAdda is our internal digital whiteboard experiment designed for effortless day-to-day
              collaboration:
            </p>
            <ul className="wb-guidance__list">
              <li>
                <strong>Digital whiteboard for the lab:</strong> This is an informal, collaborative workspace
                for day-to-day lab ideas and quick drafts. It is not an official organizational reporting
                platform.
              </li>
              <li>
                <strong>No sensitive or official data:</strong> LabAdda is strictly for informal lab ideas,
                sketches, and task tracking. Never upload classified, sensitive, or official organizational
                records here.
              </li>
              <li>
                <strong>Keep files light and relevant:</strong> Upload only necessary work-related diagrams
                and references. Avoiding huge attachments keeps our local intranet server fast and responsive.
              </li>
              <li>
                <strong>Warm and constructive etiquette:</strong> We thrive on mutual respect. Communicate
                with warmth, professional courtesy, and constructive suggestions.
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
            Your personal, persistent canvas for brainstorming, freehand sketching, chemical structures, and
            sticky notes. Everything here is strictly private to you.
          </p>
          <div className="wb-whiteboard-banner__actions">
            <Link to="/whiteboard" className="ui-button ui-button--primary ui-button--md">
              Open Canvas →
            </Link>
            <Link to="/calendar" className="ui-button ui-button--secondary ui-button--md">
              View Calendar
            </Link>
          </div>
          <div className="wb-whiteboard-banner__templates" aria-label="Whiteboard tools">
            <span className="wb-whiteboard-banner__templates-label">Tools:</span>
            <span className="wb-template-pill">🎨 Freehand sketches</span>
            <span className="wb-template-pill">📝 Sticky notes</span>
            <span className="wb-template-pill">📊 Text and diagrams</span>
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
            <div className="wb-canvas-preview__badge">Personal · Save explicitly</div>
          </div>
        </div>
      </section>

      {/* 5. Responsive 2-Column Personal Workbench Grid */}
      <div className="wb-grid">
        {/* LEFT COLUMN: Tasks & Calendar Agenda */}
        <div className="wb-grid__col wb-grid__col--main">
          {/* Card: Active Tasks & Today's Deadlines with Inline Completion */}
          <HomeTasksCard
            activeTasks={activeTasks}
            task={taskActions}
            dashboard={dashboard}
            todayStr={todayStr}
          />

          {/* Card: Today's Schedule & Events */}
          <HomeAgendaCard {...{ todayEvents, eventsError, eventsLoading, todayFormatted, timezone }} />
        </div>

        {/* RIGHT COLUMN: Quick Notes & Team Workspaces */}
        <div className="wb-grid__col wb-grid__col--side">
          {/* Card: Quick Notes & Personal Scratchpad with Category Tags */}
          <HomeNotesCard panels={panels} noteInputRef={noteInputRef} />

          {/* Card: Accessible Team Spaces with Filters & Search */}
          <HomeSpacesCard />
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
