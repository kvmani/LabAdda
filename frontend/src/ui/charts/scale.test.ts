import { describe, expect, it } from "vitest";
import { downsample } from "./downsample";
import { extent, linearScale, niceTicks, timeScale, timeTicks } from "./scale";

describe("linearScale", () => {
  it("maps the domain onto the range and back", () => {
    const scale = linearScale([0, 10], [100, 200]);
    expect(scale(0)).toBe(100);
    expect(scale(5)).toBe(150);
    expect(scale(10)).toBe(200);
    expect(scale.invert(150)).toBe(5);
  });

  it("supports an inverted range for a y axis", () => {
    expect(linearScale([0, 100], [200, 0])(25)).toBe(150);
  });

  it("maps a zero-width domain to the middle", () => {
    expect(linearScale([7, 7], [0, 100])(7)).toBe(50);
  });

  it("is the same scale for time", () => {
    expect(timeScale([1000, 3000], [0, 10])(2000)).toBe(5);
  });
});

describe("niceTicks", () => {
  it("rounds to 1, 2 or 5 steps covering the data", () => {
    expect(niceTicks(0, 97, 5)).toEqual({ ticks: [0, 50, 100], min: 0, max: 100 });
    expect(niceTicks(0, 78, 5).ticks).toEqual([0, 20, 40, 60, 80]);
    expect(niceTicks(3, 17, 5).ticks).toEqual([0, 5, 10, 15, 20]);
  });

  it("handles fractions without float noise", () => {
    expect(niceTicks(0, 0.3, 4).ticks).toEqual([0, 0.1, 0.2, 0.3]);
  });

  it("handles negative ranges", () => {
    const { ticks } = niceTicks(-12, 8, 5);
    expect(ticks[0]).toBeLessThanOrEqual(-12);
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(8);
    expect(ticks).toContain(0);
  });

  it("pads a flat range so it still has an axis", () => {
    const { ticks, min, max } = niceTicks(5, 5);
    expect(min).toBeLessThan(5);
    expect(max).toBeGreaterThan(5);
    expect(ticks.length).toBeGreaterThan(1);
    expect(niceTicks(0, 0).max).toBeGreaterThan(0);
  });

  it("falls back when the input is not finite", () => {
    expect(niceTicks(NaN, 3).ticks).toEqual([0, 1]);
  });
});

describe("timeTicks", () => {
  const HOUR = 3_600_000;

  it("aligns ticks to clock steps inside the range", () => {
    const start = 10 * HOUR + 7 * 60_000;
    const ticks = timeTicks(start, start + 6 * HOUR, 5, 0);
    expect(ticks.every((t) => t % HOUR === 0)).toBe(true);
    expect(ticks.every((t) => t >= start && t <= start + 6 * HOUR)).toBe(true);
    expect(ticks.length).toBeGreaterThanOrEqual(2);
  });

  it("puts day ticks on local midnight using the offset", () => {
    const offset = -330 * 60_000;
    const ticks = timeTicks(0, 5 * 86_400_000, 6, offset);
    expect(ticks.every((t) => (t + offset) % 86_400_000 === 0)).toBe(true);
  });

  it("returns the single time for an empty span", () => {
    expect(timeTicks(5, 5)).toEqual([5]);
  });
});

describe("extent", () => {
  it("ignores non-finite values and reports none for empty input", () => {
    expect(extent([3, NaN, -1, 9])).toEqual([-1, 9]);
    expect(extent([])).toBeUndefined();
  });
});

describe("downsample", () => {
  const many = Array.from({ length: 1000 }, (_, index) => ({ t: index, value: Math.sin(index / 9) }));

  it("leaves short series untouched", () => {
    const few = many.slice(0, 20);
    expect(downsample(few)).toBe(few);
  });

  it("reduces long series, in time order, keeping the global peak and dip", () => {
    const reduced = downsample(many, 100);
    expect(reduced.length).toBeLessThanOrEqual(100);
    expect(reduced.map((p) => p.t)).toEqual([...reduced.map((p) => p.t)].sort((a, b) => a - b));
    const values = many.map((p) => p.value);
    const kept = reduced.map((p) => p.value ?? NaN);
    expect(Math.max(...kept)).toBe(Math.max(...values));
    expect(Math.min(...kept)).toBe(Math.min(...values));
  });

  it("keeps a gap visible", () => {
    const gappy = many.map((p) => (p.t >= 500 && p.t < 520 ? { t: p.t, value: null } : p));
    expect(downsample(gappy, 100).some((p) => p.value === null)).toBe(true);
  });
});
