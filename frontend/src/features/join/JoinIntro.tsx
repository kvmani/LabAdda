/** What LabAdda is, what joining means and how an application is handled: static text only. */
export function JoinIntro() {
  return (
    <>
      {/* Friendly Notice Banner */}
      <section className="join-notice" aria-label="Voluntary participation and purpose notice">
        <h2 className="join-notice__title">
          <span aria-hidden="true">🔬</span> About LabAdda & Voluntary Joining
        </h2>
        <p className="join-notice__text">
          LabAdda is an experimental digital collaboration workspace built for our research teams on an
          air-gapped office intranet. Joining this platform is <strong>purely voluntary</strong>. It is
          designed to enhance daily convenience, transparent laboratory communication, and productivity.
        </p>
        <p className="join-notice__text">
          All members are expected to use LabAdda <strong>responsibly</strong>, for the{" "}
          <strong>greater good of collective scientific productivity</strong>, and for{" "}
          <strong>purely professional research purposes</strong>.
        </p>
        <div className="join-notice__callout">
          💡{" "}
          <em>
            LabAdda functions as a digital equivalent of our laboratory whiteboards and noticeboards. It is
            not intended for confidential, sensitive, or official secret records.
          </em>
        </div>
      </section>

      {/* Reference Section: FAQ & Scope */}
      <section className="join-info-grid" aria-label="Reference information and scope">
        {/* FAQ Card */}
        <div className="join-card">
          <h3 className="join-card__title">
            <span aria-hidden="true">❓</span> Frequently Asked Questions
          </h3>
          <div className="join-faq-list">
            <div className="join-faq-item">
              <p className="join-faq-q">Is participation mandatory?</p>
              <p className="join-faq-a">
                No. Participation is 100% voluntary for scientists, technical officers, and research scholars.
              </p>
            </div>
            <div className="join-faq-item">
              <p className="join-faq-q">What is LabAdda used for?</p>
              <p className="join-faq-a">
                Noticeboards for unit updates, live whiteboard sessions, experiment task tracking, topic
                chats, and private daily workbench notes.
              </p>
            </div>
            <div className="join-faq-item">
              <p className="join-faq-q">How are accounts approved?</p>
              <p className="join-faq-a">
                Laboratory administrators verify your affiliation against staff records and issue a secure,
                one-time activation code to set your password.
              </p>
            </div>
            <div className="join-faq-item">
              <p className="join-faq-q">Where is my data stored?</p>
              <p className="join-faq-a">
                Exclusively on our internal laboratory VM on the air-gapped intranet. Zero data ever leaves
                the premises.
              </p>
            </div>
          </div>
        </div>

        {/* Scope & Features Card */}
        <div className="join-card">
          <h3 className="join-card__title">
            <span aria-hidden="true">🚀</span> Key Capabilities & Scope
          </h3>
          <ul className="join-features-list">
            <li className="join-feature-item">
              <span aria-hidden="true">📢</span>
              <span>
                <strong>Noticeboard:</strong> Official lab announcements, pinned notices, and attachments.
              </span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">🎨</span>
              <span>
                <strong>Live Whiteboard:</strong> Multi-user scientific sketching, equations, and sticky
                notes.
              </span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">📋</span>
              <span>
                <strong>Tasks & Checklists:</strong> Research action items, assigned tasks, and deadline
                reminders.
              </span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">💬</span>
              <span>
                <strong>Intranet Chat:</strong> Focused, searchable laboratory discussions and project
                threads.
              </span>
            </li>
            <li className="join-feature-item">
              <span aria-hidden="true">🔒</span>
              <span>
                <strong>Privacy-First:</strong> Administrators never inspect personal notes or private
                whiteboard drawings.
              </span>
            </li>
          </ul>
        </div>
      </section>
    </>
  );
}
