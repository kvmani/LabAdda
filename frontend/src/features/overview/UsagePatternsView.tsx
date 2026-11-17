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

                <div
                  className="pattern-bar"
                  role="progressbar"
                  aria-valuenow={item.percentage}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div className="pattern-bar__fill" style={{ width: `${item.percentage}%` }} />
                </div>
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
              Research staff activity naturally concentrates around morning planning sessions and afternoon
              experiment trials.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
