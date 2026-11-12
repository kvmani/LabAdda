import { LineChart } from "../../ui";
import { formatDay, rangeText } from "../activity/model";
import { dayPoints } from "./model";
import type { Overview } from "./types";

/** Two 7-day charts. Days that are missing or hidden below five people are gaps, never zero. */
export function Charts({ overview, updated }: { overview: Overview; updated?: string }) {
  const { activity, response_time: response } = overview.charts;
  const period = `Last 7 days (${rangeText(overview.period)})`;
  return (
    <div className="overview-charts">
      <section aria-label="People active per day">
        {activity.state === "measured" ? (
          <LineChart
            title="People active per day"
            series={[{ label: "Active people", points: dayPoints(activity.points) }]}
            unit="people"
            period={period}
            updated={updated}
            formatTime={formatDay}
            height={180}
          />
        ) : (
          <p role="status">
            People active per day:{" "}
            {activity.state === "suppressed"
              ? "fewer than 5 people were active, so it is hidden."
              : "not measured yet."}
          </p>
        )}
      </section>
      <section aria-label="Response time per day">
        {response.state === "measured" ? (
          <LineChart
            title="Slowest response time each day"
            series={[{ label: "Response time (95th percentile)", points: dayPoints(response.points) }]}
            unit="ms"
            period={period}
            updated={updated}
            formatTime={formatDay}
            height={180}
          />
        ) : (
          <p role="status">Response time per day: not measured yet.</p>
        )}
      </section>
    </div>
  );
}
