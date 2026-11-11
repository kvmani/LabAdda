import { describe, expect, it } from "vitest";
import { chartPoints, effectiveStatus, formatAge, formatValue, overallSentence, scaleValues } from "./model";
import type { HealthItem } from "./types";

const item = (status: HealthItem["status"]): HealthItem => ({
  key: "database",
  label: "Database",
  status,
  value: 1,
  unit: "ms",
  detail: "",
  checked_at: "2026-11-11T12:00:00+00:00",
  age_seconds: 0,
  help: "troubleshooting/health-database",
  chart: null,
});

describe("health model", () => {
  it("marks old results stale but never an unsupported item", () => {
    expect(effectiveStatus(item("healthy"), 10, 15)).toBe("healthy");
    expect(effectiveStatus(item("healthy"), 61, 15)).toBe("stale");
    expect(effectiveStatus(item("unsupported"), 600, 15)).toBe("unsupported");
    expect(effectiveStatus(item("unavailable"), 600, 15)).toBe("stale");
  });

  it("formats ages and values without turning missing data into zero", () => {
    expect(formatAge(8)).toBe("8 s ago");
    expect(formatAge(300)).toBe("5 min ago");
    expect(formatAge(7200)).toBe("2 h ago");
    expect(formatValue(null, "ms")).toBe("Not measured");
    expect(formatValue(0, "ms")).toBe("0 ms");
    expect(formatValue(3600, "seconds")).toBe("60 min");
    expect(formatValue(5 * 1024 ** 3, "bytes")).toBe("5 GiB");
  });

  it("says plainly when nothing is confirmed healthy", () => {
    expect(overallSentence("healthy", 0)).toContain("working");
    expect(overallSentence("unknown", 0)).toContain("not confirmed healthy");
    expect(overallSentence("degraded", 2)).toBe("2 checks need attention.");
    expect(overallSentence("unavailable", 1)).toContain("1 check has failed");
  });

  it("scales bytes and leaves other units alone", () => {
    expect(scaleValues([5 * 1024 ** 3], "bytes")).toEqual({ factor: 1 / 1024 ** 3, unit: "GiB" });
    expect(scaleValues([], "bytes").unit).toBe("B");
    expect(scaleValues([1, 2], "ms")).toEqual({ factor: 1, unit: "ms" });
  });

  it("draws a long hole as a gap", () => {
    const rows = [
      { bucket_start: "2026-11-11T10:00:00+00:00", value: 1 },
      { bucket_start: "2026-11-11T10:01:00+00:00", value: 2 },
      { bucket_start: "2026-11-11T10:30:00+00:00", value: 3 },
    ];
    const points = chartPoints(rows, 2);
    expect(points.map((point) => point.value)).toEqual([2, 4, null, 6]);
  });
});
