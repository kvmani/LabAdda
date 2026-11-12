import { BarChart, DataTable, HeatGrid, LineChart, type Column } from "../../ui";
import {
  HOURS,
  WEEKDAYS,
  activeSeries,
  bucketFormatter,
  categoryFormatter,
  categorySeries,
  featureSeries,
  featureTotals,
  formatDay,
  heatValues,
  storageSeries,
} from "./model";
import type { SummaryCharts } from "./types";

type Total = { label: string; value: number | null };

const TOTAL_COLUMNS: Column<Total>[] = [
  { key: "label", header: "What", render: (row) => row.label },
  {
    key: "value",
    header: "Total",
    align: "end",
    render: (row) => (row.value === null ? "Not measured" : row.value.toLocaleString()),
  },
];

function TotalsTable({ caption, rows }: { caption: string; rows: Total[] }) {
  return <DataTable caption={caption} columns={TOTAL_COLUMNS} rows={rows} rowKey={(row) => row.label} />;
}

/** The site-wide charts of the Activity page (AD-08); every one offers "View as table". */
export function ActivityCharts({
  charts,
  period,
  updated,
}: {
  charts: SummaryCharts;
  period: string;
  updated?: string;
}) {
  const storage = storageSeries(charts);
  const sizes = charts.upload_sizes;
  const heat = charts.weekday_hour;
  const heatPeriod = heat.from
    ? `Since ${formatDay(Date.parse(heat.from))} (hourly figures are kept 35 days)`
    : period;
  const kinds: Total[] = charts.items_by_kind.map((kind) => ({ label: kind.label, value: kind.value }));
  return (
    <div className="activity-charts">
      <section className="activity-chart activity-chart--wide" aria-label="Active people per day">
        <LineChart
          title="Active people per day"
          series={activeSeries(charts)}
          unit="people"
          period={period}
          updated={updated}
          formatTime={formatDay}
        />
      </section>
      <section className="activity-chart activity-chart--wide" aria-label="Activity by feature">
        <BarChart
          title="Activity by feature"
          series={featureSeries(charts)}
          unit="items"
          period={period}
          updated={updated}
          formatTime={bucketFormatter(charts.features.bucket)}
          stacked
        />
        <div className="activity-totals">
          <TotalsTable caption="Totals by feature" rows={featureTotals(charts)} />
          <TotalsTable caption="Items created by kind of space" rows={kinds} />
        </div>
      </section>
      <section className="activity-chart activity-chart--wide" aria-label="Activity by weekday and hour">
        {heat.state === "unknown" ? (
          <p role="status">Activity by weekday and hour: not measured in this period.</p>
        ) : (
          <HeatGrid
            title="Activity by weekday and hour"
            period={heatPeriod}
            updated={updated}
            rows={WEEKDAYS}
            columns={HOURS}
            values={heatValues(charts)}
            unit="requests"
          />
        )}
      </section>
      <section className="activity-chart" aria-label="Storage growth">
        <LineChart
          title="Storage growth"
          series={storage.series}
          unit={storage.unit}
          period={period}
          updated={updated}
          formatTime={formatDay}
        />
      </section>
      <section className="activity-chart" aria-label="Uploads by size">
        <BarChart
          title="Uploads by size"
          series={categorySeries("Files added", sizes)}
          unit="files"
          period={period}
          updated={updated}
          formatTime={categoryFormatter(sizes)}
        />
      </section>
    </div>
  );
}
