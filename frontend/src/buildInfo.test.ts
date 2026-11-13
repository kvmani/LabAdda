import { describe, expect, it } from "vitest";
import { BUILD_LINE, CREDIT, formatBuildLine, versionLabel } from "./buildInfo";

describe("build identity", () => {
  it("spaces the beta label", () => {
    expect(versionLabel("0.0.1-beta")).toBe("0.0.1 beta");
  });

  it("shows version, short commit and date", () => {
    expect(formatBuildLine("0.0.1-beta", "7a94edc1234567890", "2026-11-13")).toBe(
      "Version 0.0.1 beta · commit 7a94edc · 2026-11-13",
    );
  });

  it("never invents a missing commit and leaves out an unknown date", () => {
    expect(formatBuildLine("0.0.1-beta", "", "")).toBe("Version 0.0.1 beta · commit unknown");
    expect(formatBuildLine("0.0.1-beta", "not a sha", "yesterday")).toBe(
      "Version 0.0.1 beta · commit unknown",
    );
  });

  it("is stamped by the build and carries the credit", () => {
    expect(BUILD_LINE.startsWith("Version 0.0.1 beta · commit ")).toBe(true);
    expect(CREDIT).toBe("Software conceived and developed by Dr. K. V. Mani Krishna, Materials Group.");
  });
});
