import { describe, expect, it } from "vitest";
import { auditUrl, fieldLabel, showValue } from "./model";

describe("audit explorer boundaries", () => {
  it("keeps the open entry out of list queries and paging out of reports", () => {
    const params = new URLSearchParams("group=access&cursor=abc&entry=7&untrusted=x");
    expect(auditUrl(params)).toBe("/admin/audit?group=access&cursor=abc");
    expect(auditUrl(params, true)).toBe("/admin/audit/export.csv?group=access");
  });

  it("shows missing values honestly and labels fields in plain words", () => {
    expect(showValue(null)).toBe("Not recorded");
    expect(showValue("steward")).toBe("steward");
    expect(fieldLabel("status_effective_on")).toBe("Status effective on");
  });
});
