import { Link } from "react-router-dom";
import type { UsagePattern } from "./types";

type Props = {
  patterns: UsagePattern[];
  peakSummary: string;
};

export function UsagePatternsView({ patterns, peakSummary }: Props) {
  return (
    <div className="usage-patterns-view">
      <section className="cockpit-panel" aria-label="Feature adoption and usage breakdown">
        <div className="cockpit-panel__header">
          <div>
            <h3 className="cockpit-panel__title">
              <span aria-hidden="true">📊</span> Feature Adoption & Usage Distribution
            </h3>
            <p className="cockpit-panel__subtitle">
              Relative popularity of collaboration tools across all research teams
            </p>
          </div>
          <Link to="/admin/activity" className="cockpit-panel__action-link">
            Historical activity →
          </Link>
        </div>

        <div className="cockpit-panel__body">
          {!patterns.length && (
            <p className="cockpit-muted">Activity is not measured or is protected for small groups.</p>
          )}
          <div className="feature-patterns-grid">
            {patterns.map((item) => (
              <div key={item.feature} className="feature-pattern-card">
                <div className="feature-pattern-card__header">
                  <span className="feature-pattern-card__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  <div>
                    <h4 className="feature-pattern-card__title">{item.feature}</h4>
                    <p className="feature-pattern-card__role">{item.role}</p>
                  </div>
                </div>

                <div className="feature-pattern-card__stats">
                  <div className="feature-pattern-card__count">{item.count} items</div>
                  <div className="feature-pattern-card__pct">{item.percentage}% of activity</div>
                </div>

                <progress
                  className="pattern-bar"
                  value={item.percentage}
                  max={100}
                  aria-label={`${item.feature}: share of published activity`}
                />
              </div>
            ))}
          </div>

          <div className="peak-hours-card">
            <div className="peak-hours-card__header">
              <span className="peak-hours-card__icon" aria-hidden="true">
                ⏰
              </span>
              <div>
                <h4 className="peak-hours-card__title">Peak Activity Pattern</h4>
                <p className="peak-hours-card__desc">{peakSummary}</p>
              </div>
            </div>
            <p className="cockpit-note">
              Patterns describe published request observations; they are not a measure of individual work or
              productivity.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
