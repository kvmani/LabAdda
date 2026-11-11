/** Pure scale and tick helpers shared by every chart (UX-09). No DOM, no dependencies. */

export type Scale = {
  /** Map a domain value to a range position. */
  (value: number): number;
  invert: (position: number) => number;
};

/** A linear map from `domain` to `range`. A zero-width domain maps to the middle of the range. */
export function linearScale(domain: [number, number], range: [number, number]): Scale {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0;
  const scale = (value: number) => (span === 0 ? (r0 + r1) / 2 : r0 + ((value - d0) / span) * (r1 - r0));
  scale.invert = (position: number) => (r1 === r0 ? d0 : d0 + ((position - r0) / (r1 - r0)) * span);
  return scale;
}

/** Time is plotted as epoch milliseconds, so a time scale is a linear scale. */
export const timeScale = linearScale;

/** Round `raw` to 1, 2, 5 or 10 times a power of ten. */
function niceStep(raw: number): number {
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  const fraction = raw / power;
  const factor = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return factor * power;
}

export type NiceTicks = { ticks: number[]; min: number; max: number };

/**
 * Tick values at round numbers that cover [min, max]. `min` and `max` of the result are the
 * outermost ticks, so a chart can use them as its domain.
 */
export function niceTicks(min: number, max: number, count = 5): NiceTicks {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return { ticks: [0, 1], min: 0, max: 1 };
  let low = Math.min(min, max);
  let high = Math.max(min, max);
  if (low === high) {
    const pad = low === 0 ? 1 : Math.abs(low) * 0.1;
    low -= pad;
    high += pad;
  }
  const step = niceStep((high - low) / Math.max(1, count - 1));
  const first = Math.floor(low / step) * step;
  const last = Math.ceil(high / step) * step;
  const ticks: number[] = [];
  const decimals = Math.max(0, -Math.floor(Math.log10(step)));
  for (let index = 0; first + index * step <= last + step / 2; index += 1) {
    ticks.push(Number((first + index * step).toFixed(decimals)));
  }
  return { ticks, min: ticks[0] ?? first, max: ticks[ticks.length - 1] ?? last };
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const TIME_STEPS = [
  MINUTE,
  5 * MINUTE,
  15 * MINUTE,
  30 * MINUTE,
  HOUR,
  3 * HOUR,
  6 * HOUR,
  12 * HOUR,
  DAY,
  2 * DAY,
  7 * DAY,
  14 * DAY,
  30 * DAY,
  90 * DAY,
  365 * DAY,
];

/**
 * Tick times (epoch ms) at clock-aligned steps inside [min, max]. `offsetMs` is the local
 * time-zone offset (as `Date.getTimezoneOffset() * 60000`) so day ticks fall on local midnight.
 */
export function timeTicks(
  min: number,
  max: number,
  count = 5,
  offsetMs = new Date(min).getTimezoneOffset() * MINUTE,
): number[] {
  if (!(max > min)) return [min];
  const wanted = (max - min) / Math.max(1, count - 1);
  const step = TIME_STEPS.find((candidate) => candidate >= wanted) ?? 365 * DAY;
  const ticks: number[] = [];
  for (let t = Math.ceil((min + offsetMs) / step) * step - offsetMs; t <= max; t += step) ticks.push(t);
  return ticks;
}

/** Smallest and largest of the finite values, or undefined when there are none. */
export function extent(values: Iterable<number>): [number, number] | undefined {
  let low = Infinity;
  let high = -Infinity;
  for (const value of values) {
    if (!Number.isFinite(value)) continue;
    if (value < low) low = value;
    if (value > high) high = value;
  }
  return low <= high ? [low, high] : undefined;
}
