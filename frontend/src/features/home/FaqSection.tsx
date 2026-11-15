import { useState } from "react";
import { Link } from "react-router-dom";

export type FaqItem = {
  id: string;
  question: string;
  category?: string;
  answer: React.ReactNode;
};

export const FAQ_ITEMS: FaqItem[] = [
  {
    id: "official-platform",
    category: "About & Scope",
    question: "Is LabAdda an official platform of our organisation?",
    answer: (
      <>
        <p>
          <strong>No.</strong> LabAdda is <strong>not an official platform</strong> of our organisation.
          It started as a small, informal internal experiment designed to make day-to-day scientific
          communication, brainstorming, whiteboard sketching, and team task coordination faster and simpler
          without bureaucratic friction.
        </p>
        <p>
          All official administrative sanctions, office circulars, procurement approvals, personnel records,
          and statutory documentation must continue to flow through our organisation's designated official
          ERP and intranet portals.
        </p>
      </>
    ),
  },
  {
    id: "expected-growth",
    category: "About & Scope",
    question: "Who can use LabAdda, and how is it expected to grow?",
    answer: (
      <p>
        LabAdda is open to all researchers, technical officers, and team members across our laboratory units,
        divisions, sections, and project teams. Because it is an experimental grassroots initiative, its usage
        is expected to grow organically over time as more colleagues try it out, find it helpful in their
        day-to-day work, and share suggestions for new capabilities.
      </p>
    ),
  },
  {
    id: "sensitive-data",
    category: "Data & Privacy",
    question: "What kind of data should I put on LabAdda? Can I share sensitive project data?",
    answer: (
      <>
        <p>
          <strong>Please keep LabAdda strictly for non-sensitive, daily collaboration.</strong>
        </p>
        <p>
          While the platform operates exclusively on our isolated intranet with strict access controls, it
          is <strong>not approved for classified, confidential, patent-sensitive, or restricted national
          research data</strong>. Think of LabAdda like your lab's physical whiteboard or coffee-table
          notepad: ideal for exploring hypotheses, discussing literature, planning experiments, and tracking
          next steps.
        </p>
      </>
    ),
  },
  {
    id: "admin-privacy",
    category: "Data & Privacy",
    question: "Can administrators read my private notes, team chats, or whiteboards?",
    answer: (
      <>
        <p>
          <strong>No.</strong> LabAdda enforces <strong>strict administrator content blindness</strong>.
          Site administrators and unit administrators manage user accounts, storage quotas, and system
          health—they can <strong>never</strong> see your message text, personal note contents, private task
          descriptions, or whiteboard drawings.
        </p>
        <p>
          Your personal tools (<em>My Whiteboard</em>, <em>My Notes</em>, <em>My Day</em>, and{" "}
          <em>My Calendar</em>) are completely isolated and visible only to you.
        </p>
      </>
    ),
  },
  {
    id: "unit-access",
    category: "Collaboration",
    question: "How does workspace and unit access work across the organisation?",
    answer: (
      <p>
        Access mirrors our natural laboratory structure:
        <br />• <strong>Upward-only hierarchy:</strong> A member of a Section automatically sees notices and
        events from their parent Division and Group. Division members cannot peek into individual Sections
        unless granted explicit Section membership.
        <br />• <strong>Projects & Groups:</strong> Completely private and flat. Only colleagues explicitly
        invited can see or participate.
      </p>
    ),
  },
  {
    id: "calendar-system",
    category: "Collaboration",
    question: "How does the Central Calendar work across units and projects?",
    answer: (
      <p>
        The central <Link to="/calendar">Calendar</Link> layers schedules into a single unified view:
        site-wide institutional seminars and holidays for everyone, division and section events for unit
        members, project milestones for project teams, and personal reminders strictly for you. All dates
        and times follow Indian Standard Time (IST).
      </p>
    ),
  },
  {
    id: "create-groups",
    category: "Collaboration",
    question: "Can I create a new group or workspace for my project or reading club?",
    answer: (
      <p>
        <strong>Yes!</strong> Any colleague can create a private collaborative group instantly from the left
        navigation bar (<Link to="/groups/new">+ New group</Link>) without needing approval from IT. For
        official institutional units (new sections, divisions, or projects), your unit administrator can
        configure them in seconds.
      </p>
    ),
  },
  {
    id: "feedback-support",
    category: "Support",
    question: "How can I share feedback, suggest an idea, or report an issue?",
    answer: (
      <p>
        We would love to hear from you! Click the <strong>Feedback</strong> button in the top navigation bar
        at any time to share your impressions, report any glitch, or request a feature. Because this is an
        active experiment, your input directly shapes what we build next! You can also explore the in-app{" "}
        <Link to="/help">Help Center</Link> for detailed guides on every feature.
      </p>
    ),
  },
];

export function FaqSection({ defaultOpenId }: { defaultOpenId?: string }) {
  const [openId, setOpenId] = useState<string | null>(defaultOpenId ?? "official-platform");

  const toggle = (id: string) => {
    setOpenId((prev) => (prev === id ? null : id));
  };

  return (
    <section className="home-faq" aria-label="Frequently Asked Questions">
      <div className="home-faq__header">
        <span className="home-faq__icon" aria-hidden="true">
          💡
        </span>
        <div>
          <h2>Frequently Asked Questions</h2>
          <p className="home-faq__tagline">
            Everything you need to know about LabAdda, its experimental purpose, and how to use it.
          </p>
        </div>
      </div>

      <div className="home-faq__list" role="region" aria-label="FAQ accordion list">
        {FAQ_ITEMS.map((item) => {
          const isOpen = openId === item.id;
          return (
            <div key={item.id} className={`home-faq__item ${isOpen ? "home-faq__item--open" : ""}`}>
              <button
                type="button"
                className="home-faq__question-btn"
                aria-expanded={isOpen}
                aria-controls={`faq-answer-${item.id}`}
                id={`faq-btn-${item.id}`}
                onClick={() => toggle(item.id)}
              >
                <span className="home-faq__question-text">
                  {item.category && <span className="home-faq__category">{item.category}</span>}
                  {item.question}
                </span>
                <span className="home-faq__toggle-icon" aria-hidden="true">
                  {isOpen ? "−" : "+"}
                </span>
              </button>
              {isOpen && (
                <div
                  id={`faq-answer-${item.id}`}
                  role="region"
                  aria-labelledby={`faq-btn-${item.id}`}
                  className="home-faq__answer"
                >
                  {item.answer}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
