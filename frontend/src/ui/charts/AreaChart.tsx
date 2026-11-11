import { TimeChart } from "./TimeChart";
import type { ChartBaseProps } from "./types";

/** Like LineChart with the area under each line filled; the value axis includes zero. */
export function AreaChart(props: ChartBaseProps) {
  return <TimeChart {...props} area />;
}
