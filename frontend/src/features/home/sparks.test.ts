import { describe, expect, it } from "vitest";
import { getDailySpark, RESEARCH_SPARKS } from "./sparks";

describe("sparks", () => {
  it("provides authentic research quotes", () => {
    expect(RESEARCH_SPARKS.length).toBeGreaterThanOrEqual(10);
    const raman = RESEARCH_SPARKS.find((s) => s.author.includes("Raman"));
    expect(raman).toBeDefined();
    expect(raman?.quote).toBeTruthy();
  });

  it("cycles sparks deterministically with offset", () => {
    const s0 = getDailySpark(0);
    const s1 = getDailySpark(1);
    expect(s0).toBeDefined();
    expect(s1).toBeDefined();
    if (RESEARCH_SPARKS.length > 1) {
      expect(s0).not.toEqual(s1);
    }
  });
});
