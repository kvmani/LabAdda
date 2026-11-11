import {
  AreaChart,
  BarChart,
  Card,
  HeatGrid,
  LineChart,
  Meter,
  Sparkline,
  type ChartPoint,
  type Series,
} from "..";

/* Fictional sample data for the chart gallery (U3). */
const HOUR = 3_600_000;
const START = Date.UTC(2026, 10, 9, 0, 0);

function hourly(count: number, make: (index: number) => number | null, step = HOUR): ChartPoint[] {
  return Array.from({ length: count }, (_, index) => ({ t: START + index * step, value: make(index) }));
}

const SESSIONS: Series = {
  label: "Sessions",
  points: hourly(48, (i) => Math.round(30 + 20 * Math.sin(i / 5))),
};
const LATENCY: Series = { label: "Response time", points: hourly(48, (i) => 120 + ((i * 37) % 60)) };
const GAPS: Series = {
  label: "Sessions",
  points: hourly(48, (i) => (i >= 14 && i < 22 ? null : Math.round(30 + 20 * Math.sin(i / 5)))),
};
const SINGLE: Series = { label: "Sessions", points: hourly(1, () => 12) };
const MANY: Series = {
  label: "Sessions",
  points: hourly(1000, (i) => Math.round(50 + 25 * Math.sin(i / 30) + ((i * 7) % 11)), 60_000),
};
const FOUR: Series[] = ["Notice", "Chat", "Tasks", "Notes"].map((label, s) => ({
  label,
  points: hourly(24, (i) => Math.round(10 + s * 6 + 8 * Math.sin(i / 4 + s))),
}));
const DAYS: Series[] = [
  { label: "Messages", points: hourly(7, (i) => [42, 55, 38, 61, 49, 12, 9][i] ?? null, 24 * HOUR) },
  { label: "Notices", points: hourly(7, (i) => [4, 6, null, 5, 7, 1, 0][i] ?? null, 24 * HOUR) },
];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, "0"));
const ACTIVITY = WEEKDAYS.map((_, day) =>
  HOURS.map((_h, hour) => {
    if (day === 6 && hour > 18) return null;
    const working = hour >= 9 && hour <= 17 && day < 5;
    return working ? 20 + ((hour * 13 + day * 7) % 30) : (hour * 3 + day) % 5;
  }),
);

const COMMON = { period: "Last 48 hours", updated: "Updated 12 s ago" };

/** Every chart with sample, empty, gap, single-point and large data. */
export function ChartsSection() {
  return (
    <div className="gallery__wide">
      <div className="gallery__row">
        <Card>
          <Sparkline label="Sessions" points={SESSIONS.points} unit="sessions" />
        </Card>
        <Card>
          <Sparkline label="Sessions with a gap" points={GAPS.points} unit="sessions" />
        </Card>
        <Card>
          <Sparkline label="Sessions, no data" points={hourly(4, () => null)} unit="sessions" />
        </Card>
      </div>
      <Card>
        <LineChart title="Sessions" series={[SESSIONS]} unit="sessions" {...COMMON} />
      </Card>
      <Card>
        <LineChart title="Sessions and response time" series={[SESSIONS, LATENCY]} {...COMMON} />
      </Card>
      <Card>
        <LineChart title="Sessions with missing samples" series={[GAPS]} unit="sessions" {...COMMON} />
      </Card>
      <Card>
        <LineChart title="One sample only" series={[SINGLE]} unit="sessions" period="Last hour" />
      </Card>
      <Card>
        <LineChart title="Nothing recorded" series={[]} period="Last 48 hours" />
      </Card>
      <Card>
        <LineChart
          title="One thousand samples"
          series={[MANY]}
          unit="sessions"
          period="Last 17 hours"
          updated="Updated just now"
        />
      </Card>
      <Card>
        <AreaChart title="Storage used" series={[SESSIONS]} unit="GB" {...COMMON} />
      </Card>
      <Card>
        <AreaChart
          title="Uses by area"
          series={FOUR}
          unit="uses"
          period="Last 24 hours"
          updated="Updated 1 min ago"
        />
      </Card>
      <Card>
        <BarChart title="Daily activity" series={DAYS} period="Last 7 days" updated="Updated 3 min ago" />
      </Card>
      <Card>
        <BarChart
          title="Daily activity, stacked"
          series={DAYS}
          stacked
          period="Last 7 days"
          updated="Updated 3 min ago"
        />
      </Card>
      <Card>
        <BarChart title="Daily activity, empty" series={[]} period="Last 7 days" />
      </Card>
      <Card>
        <HeatGrid
          title="Activity by weekday and hour"
          period="Last 4 weeks"
          updated="Updated 5 min ago"
          rows={WEEKDAYS}
          columns={HOURS}
          values={ACTIVITY}
          unit="messages"
        />
      </Card>
      <Card>
        <HeatGrid title="Activity, empty" period="Last 4 weeks" rows={WEEKDAYS} columns={HOURS} values={[]} />
      </Card>
      <Card>
        <div className="gallery__wide">
          <Meter label="Disk space" value={240} max={500} unit="GB" warnAt={400} dangerAt={475} />
          <Meter label="Disk space" value={420} max={500} unit="GB" warnAt={400} dangerAt={475} />
          <Meter label="Disk space" value={490} max={500} unit="GB" warnAt={400} dangerAt={475} />
          <Meter label="Disk space, not measured" value={null} max={500} unit="GB" />
        </div>
      </Card>
    </div>
  );
}
