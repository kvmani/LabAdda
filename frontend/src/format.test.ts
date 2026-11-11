import { describe, expect, it } from "vitest";
import { fmtBytes } from "./format";

describe("storage display preserves small measurements and unknowns", () => {
  it.each([
    [null, "Unknown"],
    [NaN, "Unknown"],
    [-1, "Unknown"],
    [0, "0 B"],
    [21, "21 B"],
    [1024, "1 KiB"],
    [1024 ** 2, "1 MiB"],
    [1024 ** 3, "1 GiB"],
  ])("%s → %s", (value, expected) => {
    expect(fmtBytes(value)).toBe(expected);
  });
});
