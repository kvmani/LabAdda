import type { KeyboardEventHandler, ReactNode } from "react";
import { useChartWidth } from "./useChartWidth";

type ChartPlotProps = {
  /** Names the plot and says how to read it. */
  label: string;
  height: number;
  /** Text for the point being read, announced and shown; null when none. */
  readout: string | null;
  handlers: {
    onKeyDown: KeyboardEventHandler<HTMLElement>;
    onFocus: () => void;
    onBlur: () => void;
  };
  /** Called with the pointer's x inside the drawing and the drawing width; x is null on leave. */
  onPointer?: (x: number | null, width: number) => void;
  /** The SVG contents for a drawing of this width. */
  children: (width: number) => ReactNode;
};

/**
 * The interactive drawing area: one tab stop, arrow-key reading, pointer reading, a visible
 * read-out and the same text in a live region for screen readers (UX-09).
 */
export function ChartPlot({ label, height, readout, handlers, onPointer, children }: ChartPlotProps) {
  const [ref, width] = useChartWidth();
  return (
    <div className="ui-chart__body">
      <div
        ref={ref}
        className="ui-chart__plot"
        role="application"
        aria-label={`${label}. Use the arrow keys to read each point.`}
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- one keyboard widget: arrow keys read points
        tabIndex={0}
        {...handlers}
        onPointerMove={(event) => {
          const box = event.currentTarget.getBoundingClientRect();
          onPointer?.(event.clientX - box.left, width);
        }}
        onPointerLeave={() => onPointer?.(null, width)}
      >
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          aria-hidden="true"
          focusable="false"
        >
          {children(width)}
        </svg>
      </div>
      <p className="ui-chart__readout" aria-hidden="true">
        {readout ?? "Focus the chart and use the arrow keys to read each value."}
      </p>
      <p className="ui-visually-hidden" role="status" aria-live="polite">
        {readout ?? ""}
      </p>
    </div>
  );
}
