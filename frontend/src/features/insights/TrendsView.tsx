import { Card, DataTable, EmptyState, LineChart, Sparkline, Tag, type Column } from "../../ui";
import {
  decisions,
  featureSeries,
  formatChange,
  formatCount,
  formatRate,
  peopleSeries,
  sparkPoints,
  TREND_WORDS,
  type Bucket,
} from "./model";
import type { FeatureMomentum, Trends } from "./types";

const BUCKETS: { key: Bucket; title: string; empty: string }[] = [
  { key: "focus", title: "Focus here", empty: "No feature is growing or carrying most of the work yet." },
  { key: "watch", title: "Look closer", empty: "No feature is losing use." },
  { key: "drop", title: "Candidates to simplify or retire", empty: "Every feature is in use." },
];

function TrendTag({ feature }: { feature: FeatureMomentum }) {
  const word = TREND_WORDS[feature.trend];
  return <Tag tone={word.tone}>{word.label}</Tag>;
}

function Decisions({ features }: { features: FeatureMomentum[] }) {
  const grouped = decisions(features);
  return (
    <div className="insights-decisions">
      {BUCKETS.map((bucket) => (
        <Card key={bucket.key} title={bucket.title} level={3}>
          {grouped[bucket.key].length === 0 ? (
            <p className="insights-muted">{bucket.empty}</p>
          ) : (
            <ul className="insights-decision-list">
              {grouped[bucket.key].map((feature) => (
                <li key={feature.key}>
                  <span className="insights-decision-name">
                    {feature.label} <TrendTag feature={feature} />
                  </span>
                  <span className="insights-muted">
                    {formatChange(feature.change)}. {feature.advice}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      ))}
    </div>
  );
}

function PeopleTiles({ trends }: { trends: Trends }) {
  const people = trends.people;
  if (!people) return null;
  const tiles = [
    {
      label: "Active people per week",
      value: formatCount(people.weekly_recent),
      note: formatChange(people.change),
    },
    {
      label: "Reach",
      value: formatRate(people.reach),
      note: `Of ${formatCount(people.accounts)} enabled accounts, in an average recent week`,
    },
    {
      label: "Return rate",
      value: formatRate(people.stickiness),
      note: "Average day's active people as a share of the week's",
    },
    { label: "Direction", value: TREND_WORDS[people.trend].label, note: "Weekly active people" },
  ];
  return (
    <ul className="insights-tiles" aria-label="People figures">
      {tiles.map((tile) => (
        <li key={tile.label} className="insights-tile">
          <p className="insights-tile__label">{tile.label}</p>
          <p className="insights-tile__value">{tile.value}</p>
          <p className="insights-muted">{tile.note}</p>
        </li>
      ))}
    </ul>
  );
}

export function TrendsView({ trends, updated }: { trends: Trends; updated?: string }) {
  if (trends.state === "unknown")
    return (
      <EmptyState title="Not measured yet">
        <p>Trends appear once LabAdda has collected a few weeks of use. Nothing is shown as zero.</p>
      </EmptyState>
    );
  if (trends.state === "suppressed")
    return (
      <EmptyState title="Hidden to protect privacy">
        <p>Every week had fewer than five active people, so figures could point to one person.</p>
      </EmptyState>
    );
  const period = `Complete weeks since ${trends.first_day}`;
  const columns: Column<FeatureMomentum>[] = [
    { key: "label", header: "Feature", render: (row) => row.label, sortValue: (row) => row.label },
    { key: "trend", header: "Direction", render: (row) => <TrendTag feature={row} /> },
    {
      key: "weekly",
      header: "Per week now",
      align: "end",
      render: (row) => formatCount(row.weekly_recent),
      sortValue: (row) => row.weekly_recent ?? -1,
    },
    {
      key: "change",
      header: `Change over ${trends.compare_weeks} weeks`,
      render: (row) => formatChange(row.change),
      sortValue: (row) => row.change ?? -Infinity,
    },
    {
      key: "share",
      header: "Share of activity",
      align: "end",
      render: (row) => formatRate(row.share),
      sortValue: (row) => row.share ?? -1,
    },
    {
      key: "per_person",
      header: "Per active person",
      align: "end",
      render: (row) => (row.per_person === null ? "Not measured" : row.per_person.toFixed(1)),
      sortValue: (row) => row.per_person ?? -1,
    },
    {
      key: "spark",
      header: "Weekly trend",
      render: (row) => <Sparkline label={row.label} points={sparkPoints(trends, row)} />,
    },
  ];
  return (
    <div className="insights-stack">
      <PeopleTiles trends={trends} />
      <section aria-labelledby="insights-decide">
        <h2 id="insights-decide" className="insights-heading">
          What to do next
        </h2>
        <p className="insights-muted">
          Compares the last {trends.compare_weeks} complete weeks with the {trends.compare_weeks} before them.
          The current week is shown but not compared, because it is not over.
        </p>
        <Decisions features={trends.features} />
      </section>
      <div className="insights-charts">
        <LineChart
          title="Use of the busiest features"
          series={featureSeries(trends)}
          unit="items"
          period={period}
          updated={updated}
        />
        <LineChart
          title="Active people per week"
          series={peopleSeries(trends)}
          unit="people"
          period={period}
          updated={updated}
        />
      </div>
      <DataTable
        caption="Feature momentum"
        columns={columns}
        rows={trends.features}
        rowKey={(row) => row.key}
        empty={{ title: "No features measured" }}
      />
    </div>
  );
}
