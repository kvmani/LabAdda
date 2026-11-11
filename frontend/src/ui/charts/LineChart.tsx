import { TimeChart } from "./TimeChart";
import type { ChartBaseProps } from "./types";

/** A measure over time, one to four series, gaps where nothing was measured (UX-09). */
export function LineChart(props: ChartBaseProps) {
  return <TimeChart {...props} area={false} />;
}
