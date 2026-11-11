import { describe, expect, it } from "vitest";
import { eventsUrl, severityPill, stateLabel } from "./model";

describe("events model", () => {
  it("passes only known filters and the cursor to the server", () => {
    const params = new URLSearchParams("state=open&severity=error&event=7&junk=1&cursor=abc");
    expect(eventsUrl(params)).toBe("/admin/events?state=open&severity=error&cursor=abc");
    expect(eventsUrl(new URLSearchParams())).toBe("/admin/events");
  });

  it("labels states and severities in plain words", () => {
    expect(stateLabel("acknowledged")).toBe("Acknowledged");
    expect(severityPill.critical.label).toBe("Critical");
    expect(severityPill.info.tone).toBe("info");
  });
});
