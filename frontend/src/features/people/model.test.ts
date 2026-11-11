import { describe, expect, it } from "vitest";
import { calendarDate, peopleUrl, unitOptions } from "./model";

describe("staff screen boundaries", () => {
  it("keeps profile state out of list queries and page cursors out of reports", () => {
    const params = new URLSearchParams("q=Ben&cursor=page2&person=staff-id&view=access&untrusted=value");
    expect(peopleUrl(params)).toBe("/admin/people?q=Ben&cursor=page2");
    expect(peopleUrl(params, true)).toBe("/admin/people/export.csv?q=Ben");
  });

  it("keeps site calendar dates unchanged and handles missing or invalid dates", () => {
    expect(calendarDate("2023-07-03")).toBe("3 Jul 2023");
    expect(calendarDate(null)).toBe("Not recorded");
    expect(calendarDate("2023-02-30")).toBe("Unknown date");
    expect(calendarDate("not-a-date")).toBe("Unknown date");
  });

  it("disambiguates sibling names and excludes projects from home-unit choices", () => {
    const options = unitOptions([
      { id: "a", name: "North", kind: "org", parent_id: null },
      { id: "b", name: "South", kind: "org", parent_id: null },
      { id: "c", name: "Sensors", kind: "org", parent_id: "a" },
      { id: "d", name: "Sensors", kind: "org", parent_id: "b" },
      { id: "e", name: "Private pilot", kind: "project", parent_id: null },
    ]);
    expect(options.map((option) => option.label)).toEqual([
      "North",
      "North / Sensors",
      "South",
      "South / Sensors",
    ]);
  });
});
