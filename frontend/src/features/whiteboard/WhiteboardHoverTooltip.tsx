import type { HoverTooltipData } from "./types";

export function WhiteboardHoverTooltip({ data }: { data: HoverTooltipData | null }) {
  if (!data) return null;
  return (
    <div className="board-tooltip" role="tooltip" style={{ left: `${data.x}px`, top: `${data.y}px` }}>
      <span className="board-tooltip__author">{data.author}</span>
      <span className="board-tooltip__meta">
        {data.kind} · {data.time}
      </span>
    </div>
  );
}
