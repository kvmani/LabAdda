/** Four mark shapes, one per series, so series differ without relying on colour (UX-09). */
export const SERIES_COUNT = 4;

/** Dash patterns for lines, matching the marker order. */
export const DASHES = ["", "7 4", "2 4", "9 3 2 3"];

type MarkProps = { shape: number; x: number; y: number; size?: number; className?: string };

export function Mark({ shape, x, y, size = 4, className }: MarkProps) {
  const kind = shape % SERIES_COUNT;
  if (kind === 0) return <circle className={className} cx={x} cy={y} r={size} />;
  if (kind === 1) {
    return <rect className={className} x={x - size} y={y - size} width={size * 2} height={size * 2} />;
  }
  const points =
    kind === 2
      ? `${x},${y - size * 1.2} ${x + size * 1.2},${y + size} ${x - size * 1.2},${y + size}`
      : `${x},${y - size * 1.3} ${x + size * 1.3},${y} ${x},${y + size * 1.3} ${x - size * 1.3},${y}`;
  return <polygon className={className} points={points} />;
}
