import { describe, it, expect } from "vitest";
import { formatSalutationName, getDynamicGreeting } from "./greetings";

describe("greetings", () => {
  it("formats salutation names with titles and first names", () => {
    expect(formatSalutationName("Dr. Bharat Kulkarni")).toBe("Dr. Bharat");
    expect(formatSalutationName("Prof. Vikram Sarabhai")).toBe("Prof. Vikram");
    expect(formatSalutationName("Shri Ramesh Rao")).toBe("Shri Ramesh");
    expect(formatSalutationName("Smt. Sita Devi")).toBe("Smt. Sita");
    expect(formatSalutationName("Ananya Sharma")).toBe("Ananya");
    expect(formatSalutationName("")).toBe("colleague");
    expect(formatSalutationName(undefined)).toBe("colleague");
  });

  it("produces time-relevant greetings for morning, afternoon, evening, and night", () => {
    // 9 AM (morning)
    const morningDate = new Date(2026, 10, 15, 9, 0, 0);
    const morningGreeting = getDynamicGreeting("Dr. Bharat Kulkarni", morningDate);
    expect(morningGreeting).toBeTruthy();
    expect(morningGreeting).toContain("Dr. Bharat");

    // 2 PM (afternoon)
    const afternoonDate = new Date(2026, 10, 15, 14, 0, 0);
    const afternoonGreeting = getDynamicGreeting("Kavita Patel", afternoonDate);
    expect(afternoonGreeting).toBeTruthy();
    expect(afternoonGreeting).toContain("Kavita");

    // 7 PM (evening)
    const eveningDate = new Date(2026, 10, 15, 19, 0, 0);
    const eveningGreeting = getDynamicGreeting("Dr. Ananya Rao", eveningDate);
    expect(eveningGreeting).toBeTruthy();
    expect(eveningGreeting).toContain("Dr. Ananya");

    // 11 PM (late night)
    const nightDate = new Date(2026, 10, 15, 23, 0, 0);
    const nightGreeting = getDynamicGreeting("Devendra Singh", nightDate);
    expect(nightGreeting).toBeTruthy();
    expect(nightGreeting).toContain("Devendra");
  });

  it("rotates greetings across calls without errors", () => {
    const d = new Date(2026, 10, 15, 10, 0, 0);
    const g1 = getDynamicGreeting("Dr. Bharat Kulkarni", d);
    const g2 = getDynamicGreeting("Dr. Bharat Kulkarni", d);
    expect(g1).toBeTruthy();
    expect(g2).toBeTruthy();
  });
});
